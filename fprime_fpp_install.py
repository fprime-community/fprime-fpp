""" install.py:

Installs the FPP tool suite based on the version of this installer package. It will use FPP_DOWNLOAD_CACHE environment
variable to pull up previously downloaded items for users that wish to install offline.
"""
import atexit
import json
import os
import platform
import re
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


TEMPORARY_VERSION_FILE = Path(tempfile.gettempdir()) / "fprime_versions.json"
FPP_TOOLS_VARIABLE = "FPP_TOOLS_VERSION"


def clean_at_exit(file_or_directory):
    """Register file for cleanup at exit"""

    def clean_version_file(path):
        """Clean up the version file iff it is created"""
        print(f"-- INFO  -- Removing: {path}")
        shutil.rmtree(path, ignore_errors=True)

    atexit.register(clean_version_file, file_or_directory)


# Force the temporary version file to be removed
clean_at_exit(TEMPORARY_VERSION_FILE)


def read_version_from_temp(file: Path, fallback=None, safe=False):
    """Reads the versioning information from temporary directory

    When an installation of the fprime package runs, it will set the versioning information in a temporary file. This
    file is read and processed to determine the FPP_TOOLS_VERSION to install. It is associated with a PPID file to
    ensure that this file was created within the same parent process tree. This ensures that it is valid.  If the PPID
    field is not set, it will assume the file is correct.
    """
    try:
        with open(file, "r") as file_handle:
            versions = json.load(file_handle)
        version = versions[FPP_TOOLS_VARIABLE]
        if safe or versions["setup_ppid"] == os.getppid():
            print(
                f"-- INFO  -- Found version {version} in {file}, overriding {fallback}"
            )
            return version
        print(
            f"-- WARN  -- {file} contained non-matching parent process id, skipping as version source"
        )
    except OSError:
        print(f"-- WARN  -- Failed to find {file}, skipping as version source")
    except KeyError:
        print(
            f"-- WARN  -- {file} did not define { FPP_TOOLS_VARIABLE }, skipping as version source"
        )
    return fallback


def setup_version():
    """Setup the version information for the fpp tools that will be installed

    There are three cases for installing fpp-tools that we care about: installing via the fprime package, installing the
    PIP package locally, and building the sdist package for the PIP repository. The priority of these cases is in-order
    from hardest to trigger to easiest:

    1. fprime package, only triggered when PIP installing fprime. Sources version from temporary file.
    2. 'sdist', must read from environment variable
    3. Local install, must read from environment variable

    The code reads these cases from 3-1 (reverse order) overriding at each step. This effectively means the version
    derived from 'fprime' when it is installing always takes precedence. Then the user's supplied environment variable
    and then only takes the default information from the package itself. It is an error if no version is found.

    The code also creates the version file, for shipping as the default with the package
    """
    version = os.environ.get(
        FPP_TOOLS_VARIABLE, None
    )  # 'sdist' and local from environment file
    version = read_version_from_temp(
        TEMPORARY_VERSION_FILE, version
    )  # fprime package install, read checking ppid

    # Check for the case when the version was not found
    if version is None:
        print(
            f"[ERROR] 'sdist' builds and local installations, must set { FPP_TOOLS_VARIABLE }environment variable"
        )
        sys.exit(1)
    return version


def get_package_version(tools_version):
    """Package version from the tool version"""
    version_match_string = r"(v\d+\.\d+\.\d+)"
    hash_match_string = r"([a-fA-F0-9]{8,40}+)"
    full_version_string = fr"{ version_match_string }-(\d+)-g{ hash_match_string }"

    hash_matcher = re.compile(hash_match_string)
    full_version_matcher = re.compile(full_version_string)

    # Base settings
    version = "v0.0.0"
    commits = "999"
    hash = "00000000"

    # Exact match of a version string, should be returned right back:
    if re.match(fr"^{ version_match_string }$", tools_version):
        return tools_version
    elif hash_matcher.match(tools_version):
        hash = tools_version[:8]
    elif full_version_matcher.match(tools_version):
        matched = full_version_matcher.match(tools_version)
        version = matched.group(1)
        commits = matched.group(2)
        hash = matched.group(3)[:8]
    return f"{ version }.dev{ commits }+g{ hash }"


__FPP_TOOLS_VERSION__ = setup_version()
PACKAGE_VERSION = get_package_version(__FPP_TOOLS_VERSION__)
WORKING_DIR = Path(tempfile.gettempdir()) / "__FPP_WORKING_DIR__"
FPP_ARTIFACT_PREFIX = "native-fpp"
FPP_COMPRESSION_EXT = ".tar.gz"
GITHUB_URL = os.environ.get("FPP_TOOLS_REPO", "https://github.com/fprime-community/fpp")
GITHUB_RELEASE_URL = "{GITHUB_URL}/releases/download/{version}/{artifact_string}"


@contextmanager
def safe_chdir(path):
    """Safely change directory, returning when done."""
    origin = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


def get_artifact_string(version: str) -> str:
    """Gets the platform string for the package. e.g. Darwin-x86_64"""
    return f"{ FPP_ARTIFACT_PREFIX }-{ platform.system() }-{ platform.machine() }{ FPP_COMPRESSION_EXT }"


def wget(url: str):
    """wget functionality to fetch a URL"""
    print(f"-- INFO  -- Fetching FPP tools at { url }", file=sys.stderr)
    try:
        urllib.request.urlretrieve(url, Path(url).name)
    except urllib.error.HTTPError as error:
        print(
            f"-- WARN  -- Failed to retrieve { url } with error: { error }",
            file=sys.stderr,
        )
        raise


def github_release_download(version: str):
    """Attempts to get FPP via the FPP release"""
    try:
        release_url = GITHUB_RELEASE_URL.format(
            GITHUB_URL=GITHUB_URL,
            version=version,
            artifact_string=get_artifact_string(version),
        )
        wget(release_url)
    except urllib.error.HTTPError as error:
        retry_likely = "404" not in str(error)
        retry_error = f"Retrying will likely resolve the problem."
        # Check if this is a real error or not available error
        if retry_likely:
            print(f"-- INFO  -- { retry_error }", file=sys.stderr)
            sys.exit(-1)


def prepare_cache_dir(cache_directory: Path, version: str) -> Path:
    """Prepare the cache directory for the installation artifact

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


def install_fpp(working_dir: Path) -> Path:
    """Installs FPP of the specified version"""
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
            print(
                "-- WARN  -- Cached/released tools not found. Falling back to git clone."
            )
            tools_install_directory = install_fpp_via_git(cache_directory, version)
        return tools_install_directory


def install_fpp_via_git(installation_directory: Path, version: str):
    """Installs FPP from git

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
        steps = [
            ["git", "clone", GITHUB_URL, str(build_directory)],
            ["git", "checkout", version],
            [
                os.path.join(build_directory, "compiler", "install"),
                str(installation_directory),
            ],
        ]
        for step in steps:
            print(f"-- INFO  -- Running { ' '.join(step) }")
            completed = subprocess.run(step, cwd=build_directory)
            if completed.returncode != 0:
                print(f"-- ERROR -- Failed to run { ' '.join(step) }")
                sys.exit(-1)

    return installation_directory


def iterate_fpp_tools(working_dir: Path) -> Iterable[Path]:
    """Iterates through FPP tools"""
    untar_possibility = working_dir / get_artifact_string(
        __FPP_TOOLS_VERSION__
    ).replace(".tar.gz", "")
    if not any(os.scandir(working_dir)):
        working_dir = install_fpp(working_dir)
    elif untar_possibility.exists() and any(os.scandir(untar_possibility)):
        working_dir = untar_possibility
    return working_dir.iterdir()


@contextmanager
def clean_install_fpp():
    """Cleanly installs FPP in subdirectory, cleaning when finished"""
    WORKING_DIR.mkdir(exist_ok=True)

    def lazy_loader():
        """Prevents the download of FPP items until actually enumerated"""
        for item in iterate_fpp_tools(WORKING_DIR):
            yield item

    yield lazy_loader()
