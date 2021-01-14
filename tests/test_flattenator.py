from flattenator import Flattenator

#
# Note that these do not test any of the push functionality.
#  This is by design.
#


def test_create_object():
    flat = _make_flat()
    assert flat.tag == "main"
    assert flat.repo == "lsstsqre/flattenatortest"
    assert flat.image_tag == "lsstsqre/flattenatortest:main"
    assert flat.layer_tag == "lsstsqre/flattenatortest:exp_main_layered"
    assert flat.flat_tag == "lsstsqre/flattenatortest:exp_main_flattened"
    assert flat.container_name == "flattenatortest_main"


def test_debug():
    flat = Flattenator(repo="lsstsqre/flattenatortest", tag="main", debug=True)
    assert flat.debug is True


def test_inspect():
    flat = _get_img()
    flat._inspect_image()
    assert flat.cfg["Cmd"][0] == "/hello.sh"
    assert flat.cfg["User"] == "405:100"
    assert flat.cfg["WorkingDir"] == "/tmp"
    assert "DESCRIPTION=Flattenator Test Container" in flat.cfg["Env"]


def test_convert():
    inp_flat = _get_img()
    inp_flat._inspect_image()
    inp_flat._extract_docker_change()
    inp_flat._tag_layered_image()
    inp_flat._create_container()
    saved_exc = None
    try:
        inp_flat._create_flattened_image()
        outp_flat = Flattenator(
            repo="lsstsqre/flattenatortest", tag="exp_main_flattened"
        )
        outp_flat._inspect_image()
        assert outp_flat.cfg["Cmd"][0] == "/hello.sh"
        assert outp_flat.cfg["User"] == "405:100"
        assert outp_flat.cfg["WorkingDir"] == "/tmp"
        assert "DESCRIPTION=Flattenator Test Container" in outp_flat.cfg["Env"]
        assert len(outp_flat.layers) == 1
    except Exception as exc:
        saved_exc = exc
    try:
        inp_flat._cleanup()
    except Exception as exc:
        if saved_exc:
            # Raise the older one
            raise (saved_exc)
        saved_exc = exc
    if saved_exc:
        # If something went wrong...
        raise (saved_exc)


def _make_flat():
    flat = Flattenator(repo="lsstsqre/flattenatortest", tag="main")
    return flat


def _get_img():
    flat = _make_flat()
    flat._pull_image()
    return flat
