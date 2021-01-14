# Flattenator

Flattenator takes a layered Docker image as input, and replaces it with a
flattened single-layer image as output, preserving metadata in so far as
possible.

## Operation

Flattenator must be invoked from a machine with Python 3 (and click)
installed, and docker must be in the `PATH`.  Further, `docker login`
must have already been run to allow the running user to push an image.

Flattenator will download the image requested, push that image with the
tag `exp_{tag}_layered` (so as not to destroy the initial image),
flatten the image, and then push the flattened image under both the
original tag and `exp_{tag}_flattened`.
