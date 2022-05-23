# fprime-fpp Package Repo

"Abandon all hope ye who enter here"  -- Dante

With that out of the way, this package is designed to help install the FPP tool suite of specific versions into the
user's path. This document will explain the basic operation of this package and how to use it.

## Installation

The basic installation of the FPP tools using this package normally flows from some fprime package who is designating
the FPP tools version. These two use cases are shown below and will install the fprime-approved version of the FPP tools
for that version of fprime.

The version of the `fprime-fpp` required to install the FPP tools must ship with a default FPP tools version with the
same set of FPP files as the desired version. This package should be rereleased any time a tool is added or removed from
the list of FPP tools.

**Install Via Cloned fprime**

```bash
pip install /path/to/fprime/
```

**Install Via Released fprime**

```bash
pip install fprime
```

Some users may wish to install a specific version of the FPP tools for testing purposes. This is easily achieved through
direct installation of this package with the environment variable `FPP_TOOLS_VERSION` specified.  **Note:** the
environment variable is ignored when installing through the `fprime` package.

```bash
FPP_TOOLS_VERSION=<version> pip install "git+https://github.com/fprime-community/fprime-fpp.git"
```

**Warning:** this package `fprime-fpp` may never be installed with the `-e` flag nor from PyPI. Thus, users must use the
git url for installation as above.

When building this package for release, users must build a source distribution and only a source distribution. This is
done with the following command and again must supply a set version of FPP tools this release is being built for.

```bash
cd /path/to/fprime-fpp/
FPP_TOOLS_VERSION=<version> python3 setup.py sdist
```

## Why? Or How I Learned to Stop Worrying...

By now, you've likely concluded that this is a fairly complicated way of delivering a set of executables to end users.
At this point it is worth a explanation as to why it was done. The requirements that led to this abomination are
summarized as: "it must be easy". To be precise:

1. The `fprime` repository is the source-of-truth for the FPP version to be used
2. `fprime` can specify different versions per-commit
3. It must be simple for the user to install the FPP tools
4. Formally released FPP tools as native executables must be supported
5. Non-released source distributions of FPP must be supported

As can be seen, this is a tall order that should require a custom installation script. However, there are some other
nice-to-have features that are considered.

1. FPP tools should live with the other F´ tools (e.g. fprime-util and fprime-gds)
2. FPP tools should be installable via the same installation step as F´ tools and F´
3. Virtual environments or equivalent should be supported

All this leads to two options:

1. Build a very complicated installation script that acts like PIP, installs to PIP's directories, but is not PIP
2. Corrupt PIP into performing the installation of these tools despite the fact that they are not python

Both are terrible options, but nothing short of terrible would meet these high-bar requirements.

## How? ...and Love Corrupting PIP

First and foremost, python aficionados should stop reading now. Nothing lies past save misery and despair. You have been
warned. Next, understand that PIP was not designed to support nor document any of this and, as such, there are a few
extra constraints to meet:

**PIP Curiosities**
1. PIP packages have limited size. Binary FPP compilations cannot be packaged inside the PIP distribution.
2. PIP runs and reruns setup.py steps. Care must be taken when handling expensive steps like downloading and compiling.
3. PIP installs each package using an individual subprocess. No access to the parent process is possible.
4. PIP and setup.py don't make argument inputs easy. Environment variables may be used.
5. In order to install and uninstall properly, PIP needs a list of files.

The basic idea is simple: when installing this package, download the correct binary release or failing that, clone the
source and build it. Simple.  There are really two complicated bits: communicating the version, and listing the needed
files.

### Version Communication

The version field must be communicated to the process and has to be supported from several distinct places. In order of
precedence, these are:

1. From the `fprime` package actively being installed
2. From the user

**Versioning with fprime**

Item #1 immediately runs afoul of "PIP curiosity #3" in that the installation of the active `fprime` package is in a
distinct separate subprocess from the installation of the packages it depends on. Thus, environment variables cannot
be set to side-load data, nor can arguments be passed due to curiosity #4. However, empirical testing has shown that the
temporary directory available to PIP can be used.

**Thus**, when installing from the `fprime` package, the version is communicated from one package to the other using a
file written to the temporary directory PIP uses.  To ensure safety, this method ships the parent process id in that
file, and it is checked during installation as a way to prevent garbage files from creating garbage installations. The
temp file is also removed when the `fprime-fpp` installation is done further limiting the risk of failure.

**Versioning from User**

Item #2 is complicated by "PIP curiosity #2". To mitigate this fact, input is supplied to the pip install, when
installing directly, via an environment variable. The name `FPP_TOOLS_VERSION` was chosen and should not be changed
lest one suffer unforeseen consequences.

### Building the Package: Shadows and Lazy Evaluation

Finally, to offset "PIP Curiosity #1, #2, and #5" the building of the package must be non-standard. This is done by
building a package containing zero-length files that act as placeholders, or shadows, of the files that are intended to
be installed. Building the source distribution for a particular version of FPP tools downloads the tools and touches 
these shadows. The zero-length touched files are then shipped.

When installing the package, these zero-length touch files are overwritten just before installation with the real
executable files. The result is that the package contains valid metadata but never stores the large files on the PIP
repository.

Lazy evaluation of the files is also used. Generators are created around the files and when evaluated the files are
downloaded. If evaluated again, the cached versions are used thus preventing all but the single download.

