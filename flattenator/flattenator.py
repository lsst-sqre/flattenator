#!/usr/bin/env python3

import click
import json
import logging
import subprocess


@click.command()
@click.argument("tag")
@click.option(
    "--repo",
    "-r",
    envvar="FLATTENATOR_REPO",
    default="lsstsqre/sciplat-lab",
    help="Repository name ['lsstsqre/sciplat-lab'].",
)
@click.option("--debug", "-d", envvar="DEBUG", is_flag=True)
def standalone(repo: str, tag: str, debug: bool = False):
    """Flatten a repository."""
    cl = Flattenator(repo=repo, tag=tag, debug=debug)
    cl.flatten()


class Flattenator:
    """Construct this with a tag and a repo, and optionally a debug bool."""

    def __init__(self, repo: str, tag: str, debug: bool = False):
        if not repo or not tag:
            raise ValueError("Both repo and tag must be specified!")
        self.repo = repo
        self.tag = tag
        self.image_tag = f"{repo}:{tag}"
        self.flat_tag = f"{repo}:exp_{tag}_flattened"
        self.layer_tag = f"{repo}:exp_{tag}_layered"
        imgname = repo.split("/")[-1]
        self.container_name = f"{imgname}_{tag}"
        self.debug = debug
        self.layers = None
        self.cmd = None
        self.env = None
        self.expose = None
        self.onbuild = None
        self.user = None
        self.volume = None
        self.workdir = None
        self.change = None
        self.log = logging.getLogger(__name__)
        if self.debug:
            self.log.setLevel(logging.DEBUG)
            self.log.debug("Debug logging enabled.")
        ch = logging.StreamHandler()
        if self.debug:
            ch.setLevel(logging.DEBUG)
        self.log.addHandler(ch)

    def flatten(self):
        """Pull an image, extract metadata, flatten, import with
        metadata, and then push both the flattened and layered images
        with different tags.
        """
        self._pull_image()
        self._inspect_image()
        if len(self.layers) < 2:
            self._reject_preflattened()
            return
        self._extract_docker_change()
        self._push_layered_image()
        self._create_container()
        self._create_flattened_image()
        self._push_flattened_image()
        self._overwrite_image()
        self._cleanup()

    def _reject_preflattened(self):
        self.log.warning(f"Image {self.image_tag} is already flattened!")
        self.log.debug(f"Removing image {self.image_tag}")
        subprocess.run(["docker", "rmi", self.image_tag])

    def _pull_image(self):
        self.log.debug(f"Pulling image {self.image_tag}")
        subprocess.run(
            ["docker", "pull", self.image_tag], check=True, capture_output=True
        )

    def _inspect_image(self):
        proc = subprocess.run(
            ["docker", "inspect", self.image_tag],
            check=True,
            capture_output=True,
        )
        output = proc.stdout.decode("utf-8")
        outer_obj = json.loads(output)
        obj = outer_obj[0]
        self.layers = obj["RootFS"]["Layers"]
        self.log.debug(f"Layers: {self.layers}")
        self.cfg = obj["Config"]
        self.log.debug(f"Config: {self.cfg}")

    def _extract_docker_change(self):
        # The --change option will apply Dockerfile instructions to the image
        #  that is created. Supported Dockerfile instructions:
        #  CMD|ENTRYPOINT|ENV|EXPOSE|ONBUILD|USER|VOLUME|WORKDIR
        #
        # I think all we need are CMD, ENTRYPOINT, ENV, USER, and WORKDIR
        change = []
        cs = "--change"
        user = self.cfg.get("User")
        if user:
            change.extend([cs, f"USER {user}"])
        workdir = self.cfg.get("WorkingDir")
        if workdir:
            change.extend([cs, f"WORKDIR {workdir}"])
        env = self.cfg.get("Env")
        if env:
            estr_l = ["ENV"]
            for line in list(env):
                (kk, val) = line.split("=", 1)
                estr_l.append(f"{kk}='{val}' ")
            change.extend([cs, " ".join(estr_l)])
        ep = self.cfg.get("Entrypoint")
        if ep:
            epstr = ""
            for ex in ep:
                if epstr:
                    epstr += ", "
                epstr += f"'{ex}'"
            change.extend([cs, f"ENTRYPOINT [{epstr}]"])
        cmd = self.cfg.get("Cmd")
        if cmd:
            cmdstr = ""
            for cx in cmd:
                if cmdstr:
                    cmdstr += ","
                cmdstr += f'"{cx}"'
            change.extend([cs, f"CMD [{cmdstr}]"])
        self.log.debug(f"Change: {change}")
        self.change = change

    def _tag_layered_image(self):
        # This is broken out from the push to make testing easier.
        self.log.debug(f"Tagging {self.image_tag} as {self.layer_tag}")
        subprocess.run(
            ["docker", "tag", self.image_tag, self.layer_tag],
            check=True,
            capture_output=True,
        )

    def _push_layered_image(self):
        self._tag_layered_image()
        self.log.debug(f"Pushing {self.layer_tag}")
        subprocess.run(
            ["docker", "push", self.layer_tag], check=True, capture_output=True
        )

    def _create_container(self):
        self._remove_container()
        self.log.debug(f"Creating docker container {self.container_name}")
        subprocess.run(
            [
                "docker",
                "run",
                "--name",
                self.container_name,
                self.image_tag,
                "/bin/true",
            ],
            check=True,
            capture_output=True,
        )

    def _remove_container(self):
        self.log.debug(f"Removing docker container {self.container_name}")
        subprocess.run(
            ["docker", "rm", self.container_name],
            check=False,
            capture_output=True,
        )

    def _create_flattened_image(self):
        export_cmd = ["docker", "export", self.container_name]
        import_cmd = ["docker", "import"]
        if self.change:
            import_cmd.extend(self.change)
        import_cmd.extend(["-", self.flat_tag])
        self.log.debug(f"Export cmd: {export_cmd}")
        self.log.debug(f"Import cmd: {import_cmd}")
        p1 = subprocess.Popen(args=export_cmd, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(args=import_cmd, stdin=p1.stdout)
        p1.stdout.close()
        p2.communicate()

    def _push_flattened_image(self):
        self.log.debug(f"Pushing {self.flat_tag}")
        subprocess.run(
            ["docker", "push", self.flat_tag], check=True, capture_output=True
        )

    def _overwrite_image(self):
        self.log.debug(f"Tagging {self.flat_tag} as {self.image_tag}")
        subprocess.run(
            ["docker", "tag", self.flat_tag, self.image_tag],
            check=True,
            capture_output=True,
        )
        self.log.debug(f"Pushing new {self.image_tag}")
        subprocess.run(
            ["docker", "push", self.image_tag], check=True, capture_output=True
        )

    def _cleanup(self):
        self._remove_container()
        for img in [self.flat_tag, self.layer_tag, self.image_tag]:
            self.log.debug(f"Removing image {img}")
            subprocess.run(
                ["docker", "rmi", img], check=True, capture_output=True
            )
            subprocess.run(
                ["docker", "image", "prune", "-f"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["docker", "builder", "prune", "-f"],
                check=True,
                capture_output=True,
            )


if __name__ == "__main__":
    standalone()
