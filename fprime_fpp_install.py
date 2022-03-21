""" install.py:

Installs the FPP tool suite based on the version of this installer package. It will use FPP_DOWNLOAD_CACHE environment
variable to pull up previously downloaded items for users that wish to install offline.
"""
import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import urllib.error

from pathlib import Path
from typing import Iterable
from contextlib import contextmanager


def setup_version():
    """ Setup a version python file """
    import setuptools_scm
    with open("fprime_fpp_version.py", "w") as file_handle:
        scm_version = setuptools_scm.get_version('.', relative_to=__file__)
        file_handle.write(f"__VERSION__ = '{ scm_version }'")

try:
    setup_version()
except ImportError:
    pass
from fprime_fpp_version import __VERSION__

# Constants for easy configuration
WORKING_DIR = "__FPP_WORKING_DIR__"
FPP_ARTIFACT_PREFIX = "native-fpp"
FPP_COMPRESSION_EXT = ".tar.gz"
GITHUB_RELEASE_URL = "https://github.com/fprime-community/fpp/releases/download/v{version}/{artifact_string}"


@contextmanager
def safe_chdir(path):
    """ Safely change directory, returning when done. """
    origin = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


def get_artifact_string(version: str) -> str:
    """ Gets the platform string for the package. e.g. Darwin-x86_64 """
    return f"{ FPP_ARTIFACT_PREFIX }-{ platform.system() }-{ platform.machine() }{ FPP_COMPRESSION_EXT }"


def wget(url: str):
    """ wget functionality to fetch a URL """
    print(f"--INFO-- Fetching FPP tools at { url }", file=sys.stderr)
    try:
        urllib.request.urlretrieve(url, Path(url).name)
    except urllib.error.HTTPError as error:
        print(f"-- ERROR -- Failed to retrieve { url } with error: { error }", file=sys.stderr)
        raise


def github_release_download(version: str):
    """ Attempts to get FPP via the FPP release """
    try:
        release_url = GITHUB_RELEASE_URL.format(version=version, artifact_string=get_artifact_string(version))
        wget(release_url)
    except urllib.error.HTTPError as error:
        retry_likely = "404" not in str(error)
        supported_error = f"Native tools { version } not supported for { platform.system() }-{ platform.machine() }."
        retry_error = f"Retrying will likely resolve the problem."
        message = supported_error if not retry_likely else retry_error
        print(f"-- INFO -- { message }", file=sys.stderr)
        sys.exit(-1)


def prepare_cache_dir(cache_directory: Path, version: str):
    """ Prepare the cache directory for the installation artifact

    Returns:
        Path to install if the cache directory is ready, None if not (usually no artifacts available)
    """
    artifact = cache_directory / get_artifact_string(version)
    if not artifact.exists():
        return None
    # Decompress tarfile in preparation for installation
    output_dir = Path(str(artifact).replace(".tar.gz", ""))
    with tarfile.open(artifact) as archive:
        archive.extractall(".")
    return output_dir


def install_fpp(working_dir: Path) -> Iterable[Path]:
    """ Installs FPP of the specified version """
    version = __VERSION__

    cache_directory = Path(os.environ.get("FPP_DOWNLOAD_CACHE", working_dir))

    # Put everything in the current working directory
    with safe_chdir(working_dir):
        # Cache directory not supplied, must download the artifacts.
        if working_dir == cache_directory:
            github_release_download(version)

        # Check cache/download directory for artifact.
        tools_install_directory = prepare_cache_dir(cache_directory, version)
        if not tools_install_directory:
            print("-- ERROR -- Cache directory must supply .tar.gz of tools")
            sys.exit(1)
            #TODO: clone_and_build(version)
        return tools_install_directory.iterdir()


@contextmanager
def clean_install_fpp():
    """ Cleanly installs FPP in subdirectory, cleaning when finished"""
    origin = os.getcwd()
    working_dir = Path(origin) / WORKING_DIR
    working_dir.mkdir(exist_ok=True)

    def lazy_loader():
        """ Prevents the download of FPP items until actually enumerated """
        for item in install_fpp(working_dir):
            yield item
    try:
        yield lazy_loader()
    # When done clean-up that created directory
    finally:
        shutil.rmtree(working_dir, ignore_errors=True)

