import importlib
import sys
import textwrap
from pathlib import Path

import pytest

ASSETS_PATH = Path(__file__).parent / "assets"

TEST_ASSETS = (
    ASSETS_PATH,
    ASSETS_PATH / "multipleroots",
    ASSETS_PATH / "namespacepackages" / "locationone",
    ASSETS_PATH / "namespacepackages" / "locationtwo",
    ASSETS_PATH / "caching",
)

# Add test assets to the Python path.
sys.path.extend([str((ASSETS_PATH / path).resolve()) for path in TEST_ASSETS])


@pytest.fixture
def write_files(tmp_path, monkeypatch):
    """
    Returns a function that writes files to a temporary directory that is on sys.path, so that the
    packages they contain can be found by build_graph.

    The function takes a dict mapping file paths (relative to the temporary directory) to their
    contents. It returns the directory that the files were written to. A different directory
    (relative to the temporary directory) can be passed as root, which is useful for creating
    namespace packages that span several directories.
    """

    modules_before = set(sys.modules)

    def write(files: dict[str, str], root: str = ".") -> Path:
        root_directory = tmp_path / root
        for relative_path, contents in files.items():
            path = root_directory / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(contents), encoding="utf-8")
        monkeypatch.syspath_prepend(str(root_directory))
        importlib.invalidate_caches()
        return root_directory

    yield write

    # Finding a package can import its parents, so don't let them leak between tests.
    for module_name in set(sys.modules) - modules_before:
        del sys.modules[module_name]
