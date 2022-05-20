""" install.py:

Installs the FPP tool suite based on the version of this installer package. It will use FPP_DOWNLOAD_CACHE environment
variable to pull up previously downloaded items for users that wish to install offline.
"""
import atexit
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.error

from pathlib import Path
from typing import Iterable
from contextlib import contextmanager


VERSION_FILE = "fprime_fpp_version.py"
FPP_TOOLS_VARIABLE = "FPP_TOOLS_VERSION"


def clean_version_file():
    """ Clean up the version file iff it is created """
    try:
        os.remove(VERSION_FILE)
    except OSError:
        pass


def setup_version():
    """ Setup a version python file

    In order to install from PIP directly, without a dependence on setuptools_scm, we need to publish as part of the
    package a version file that will carry the version of the package itself. It should also carry the default FPP tools
    version for the case when the package is installed directly via `pip install fprime-fpp`.

    This code will fail with an import error when the writen file is published
    """
    try:
        import setuptools_scm
        environment_fpp_version = os.environ[FPP_TOOLS_VARIABLE]
        atexit.register(clean_version_file)
        with open(VERSION_FILE, "w") as file_handle:
            scm_version = setuptools_scm.get_version('.', relative_to=__file__)
            file_handle.write(f"__VERSION__ = '{ scm_version }'\n")
            file_handle.write(f"__FPP_TOOLS_DEFAULT_VERSION__ = '{ environment_fpp_version }'\n")
    except ImportError:
        print("[ERROR] 'setuptools_scm' package required for source distribution build ")
        sys.exit(1)
    except KeyError as exception:
        print(f"[ERROR] Environment variable {exception} must be set")
        sys.exit(1)


# First attempt to import the version file. This will exist in the packaged version, but not in locally installed or
# built code. Locally built or installed versions will generate the file but also need setuptools_scm and the
# FPP_TOOLS_VERSION environment variable.
try:
    from fprime_fpp_version import __VERSION__, __FPP_TOOLS_DEFAULT_VERSION__
except ImportError:
    setup_version()
    from fprime_fpp_version import __VERSION__, __FPP_TOOLS_DEFAULT_VERSION__
__PACKAGE_VERSION__ = __VERSION__
__FPP_TOOLS_VERSION__ = os.environ.get(FPP_TOOLS_VARIABLE, __FPP_TOOLS_DEFAULT_VERSION__)


# Constants for easy configuration
WORKING_DIR = "__FPP_WORKING_DIR__"
FPP_ARTIFACT_PREFIX = "native-fpp"
FPP_COMPRESSION_EXT = ".tar.gz"
GITHUB_URL = os.environ.get("FPP_TOOLS_REPO", "https://github.com/fprime-community/fpp")
GITHUB_RELEASE_URL = "{GITHUB_URL}/releases/download/{version}/{artifact_string}"


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
    print(f"-- INFO  -- Fetching FPP tools at { url }", file=sys.stderr)
    try:
        urllib.request.urlretrieve(url, Path(url).name)
    except urllib.error.HTTPError as error:
        print(f"-- WARN  -- Failed to retrieve { url } with error: { error }", file=sys.stderr)
        raise


def github_release_download(version: str):
    """ Attempts to get FPP via the FPP release """
    try:
        release_url = GITHUB_RELEASE_URL.format(GITHUB_URL=GITHUB_URL, version=version,
                                                artifact_string=get_artifact_string(version))
        wget(release_url)
    except urllib.error.HTTPError as error:
        retry_likely = "404" not in str(error)
        retry_error = f"Retrying will likely resolve the problem."
        # Check if this is a real error or not available error
        if retry_likely:
            print(f"-- INFO  -- { retry_error }", file=sys.stderr)
            sys.exit(-1)


def prepare_cache_dir(cache_directory: Path, version: str) -> Path:
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
    version = __FPP_TOOLS_VERSION__

    cache_directory = Path(os.environ.get("FPP_DOWNLOAD_CACHE", working_dir))

    # Put everything in the current working directory
    with safe_chdir(working_dir):
        # Cache directory not supplied, must download the artifacts.
        if working_dir == cache_directory:
            github_release_download(version)

        # Check cache/download directory for artifact.
        tools_install_directory = prepare_cache_dir(cache_directory, version)
        if not tools_install_directory:
            print("-- WARN  -- Cache directory must supply .tar.gz of tools")
            tools_install_directory = install_fpp_via_git(cache_directory, version)
        return tools_install_directory.iterdir()


def install_fpp_via_git(installation_directory: Path, version: str):
    """ Installs FPP from git

    Should FPP not be available as a published version, this will clone the FPP repo, checkout, and build the FPP tools
    for the given version. This requires the following tools to exist on the system: git, sh, java, and sbt. These tools
    will be checked and then the process will run and intall into the specified directory.

    Args:
        installation_directory: directory to install into
        version: FPP tools version to install
    """
    tools = ["git", "sh", "java", "sbt"]
    for tool in tools:
        if not shutil.which(tool):
            print(f"-- ERROR -- {tool} must exist on PATH")
            sys.exit(-1)
    with tempfile.TemporaryDirectory() as build_directory:
        steps = [["git", "clone", GITHUB_URL, str(build_directory)],
                 ["git", "checkout", version],
                 [os.path.join(build_directory, "compiler", "install"), str(installation_directory)]]
        for step in steps:
            print(f"-- INFO  -- Running { ' '.join(step) }")
            completed = subprocess.run(step, cwd=build_directory)
            if completed.returncode != 0:
                print(f"-- ERROR -- Failed to run { ' '.join(step) }")
                sys.exit(-1)
    return installation_directory


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
