# FPP Tools Package

The F´ project releases native versions of the FPP tools for several common platforms (Darwin, Linux). This PIP package
is designed to easily install these tools into the same area as the python-based tools (fprime-util, fprime-gds).

To install:

```bash
pip install fprime-fpp
```

**WARNING**: users on unsupported platforms must still install fpp using `sbt`.

**Note:** the above command may occasionally with a network exception (node not available). Correcting this is as easy
as waiting a moment and trying again.

## Developer Warning

For developers who stumble onto this package, it is recommended that you do not emulate the patterns seen here. They fly
in the face of recommendations from the Python Packaging Authority. The reason this is done is for the following
reasons specific to this codebase:

1. Scala does not have `pip` functionality nor is it eay to build the native tools variants
2. F´ users often place tools in a virtual environment, and these tools need also reside there
3. These tools need to fall into the same dependency management as `fprime-util` and `fprime-gds` packages
4.PyPI has file and project limits, which the large native executables do not play nicely with.

For these reasons, this pattern is maintained.