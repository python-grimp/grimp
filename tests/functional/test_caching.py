import json
import logging
import shutil
import tempfile
from pathlib import Path

import pytest

from grimp import build_graph

"""
For ease of reference, these are the imports of all the files:

cachingpackage: None
cachingpackage.one: None
cachingpackage.one.alpha: sys, pytest
cachingpackage.one.beta: cachingpackage.one.alpha
cachingpackage.one.gamma: cachingpackage.one.beta
cachingpackage.one.delta: None
cachingpackage.one.delta.blue: None
cachingpackage.two: None:
cachingpackage.two.alpha: cachingpackage.one.alpha
cachingpackage.two.beta: cachingpackage.one.alpha
cachingpackage.two.gamma: cachingpackage.two.beta, cachingpackage.utils
cachingpackage.utils: cachingpackage.one, cachingpackage.two.alpha

"""

CACHING_PATH = Path(__file__).parent.parent / "assets" / "caching"
PACKAGE_COPY_SOURCE = CACHING_PATH / "cachingpackage_to_copy"
PACKAGE_COPY_DESTINATION = CACHING_PATH / "cachingpackage"


@pytest.fixture
def copied_cachingpackage():
    """
    Makes a copy of caching package and then deletes it after the test.
    """
    if PACKAGE_COPY_DESTINATION.exists():
        shutil.rmtree(str(PACKAGE_COPY_DESTINATION))
    shutil.copytree(str(PACKAGE_COPY_SOURCE), str(PACKAGE_COPY_DESTINATION))
    yield "cachingpackage"
    shutil.rmtree(str(PACKAGE_COPY_DESTINATION))


def test_build_graph_uses_cache(copied_cachingpackage):
    with tempfile.TemporaryDirectory() as cache_dir:
        graph = build_graph("cachingpackage", cache_dir=cache_dir)

        real_import_details = [
            {
                "importer": "cachingpackage.two.alpha",
                "imported": "cachingpackage.one.alpha",
                "is_lazy": False,
                "line_contents": "from ..one import alpha",
                "line_number": 1,
            },
        ]
        assert (
            graph.get_import_details(
                importer="cachingpackage.two.alpha",
                imported="cachingpackage.one.alpha",
            )
            == real_import_details
        )

        meta_file = Path(cache_dir) / "cachingpackage.meta.json"
        # Blake2B 20-character hash of "cachingpackage".
        data_file = Path(cache_dir) / "27aa562ad2a4745eb20ecf156430dbfeb0e90610.data.json"

        assert meta_file.exists()
        assert data_file.exists()

        # Edit the contents of the cache.
        snippet = "from ..one import alpha"
        replacement = snippet + "  # Inserted by test"
        _manipulate_data_file(data_file, snippet, replacement)

        graph = build_graph("cachingpackage", cache_dir=cache_dir)

        # Reloading the graph should use the cache.
        manipulated_import_details = [
            {
                "importer": "cachingpackage.two.alpha",
                "imported": "cachingpackage.one.alpha",
                "is_lazy": False,
                "line_contents": replacement,
                "line_number": 1,
            },
        ]
        assert (
            graph.get_import_details(
                importer="cachingpackage.two.alpha",
                imported="cachingpackage.one.alpha",
            )
            == manipulated_import_details
        )

        # Touch the file in question.
        (PACKAGE_COPY_DESTINATION / "two" / "alpha.py").touch()

        # Now shouldn't use the cache.
        graph = build_graph("cachingpackage", cache_dir=cache_dir)
        assert (
            graph.get_import_details(
                importer="cachingpackage.two.alpha",
                imported="cachingpackage.one.alpha",
            )
            == real_import_details
        )


def test_cache_preserves_is_lazy():
    with tempfile.TemporaryDirectory() as cache_dir:
        # First build populates the cache from source.
        build_graph("lazyimports", cache_dir=cache_dir)

        # Second build reads the imports back from the cache.
        graph = build_graph("lazyimports", cache_dir=cache_dir)

        assert graph.get_import_details(
            importer="lazyimports.one", imported="lazyimports.two"
        ) == [
            {
                "importer": "lazyimports.one",
                "imported": "lazyimports.two",
                "is_lazy": True,
                "line_number": 2,
                "line_contents": "lazy from lazyimports import two",
            }
        ]


def test_data_file_records_version_and_is_lazy(copied_cachingpackage):
    with tempfile.TemporaryDirectory() as cache_dir:
        build_graph("cachingpackage", cache_dir=cache_dir)

        data_file = Path(cache_dir) / "27aa562ad2a4745eb20ecf156430dbfeb0e90610.data.json"
        data = json.loads(data_file.read_text())

        assert data["version"] == 2
        # Each import is serialized as [imported, is_lazy, line_number, line_contents],
        # matching the field order of the get_import_details dict.
        assert data["imports_by_module"]["cachingpackage.two.alpha"] == [
            ["cachingpackage.one.alpha", False, 1, "from ..one import alpha"]
        ]


def test_cache_with_different_version_is_rebuilt(copied_cachingpackage, caplog):
    with tempfile.TemporaryDirectory() as cache_dir:
        build_graph("cachingpackage", cache_dir=cache_dir)

        data_file = Path(cache_dir) / "27aa562ad2a4745eb20ecf156430dbfeb0e90610.data.json"
        # Simulate a cache file written by a different (e.g. older) format: no version field,
        # legacy 3-tuple rows, and bogus line contents. If this file were mistakenly used, the
        # details below would contain the bogus contents instead of the real ones.
        legacy = {
            "cachingpackage.two.alpha": [["cachingpackage.one.alpha", 1, "BOGUS legacy contents"]]
        }
        data_file.write_text(json.dumps(legacy))

        with caplog.at_level(logging.INFO):
            graph = build_graph("cachingpackage", cache_dir=cache_dir)

        # The mismatched cache is ignored (not treated as corrupt) and rebuilt from source.
        assert any("different version of Grimp" in record.message for record in caplog.records)
        assert graph.get_import_details(
            importer="cachingpackage.two.alpha",
            imported="cachingpackage.one.alpha",
        ) == [
            {
                "importer": "cachingpackage.two.alpha",
                "imported": "cachingpackage.one.alpha",
                "is_lazy": False,
                "line_contents": "from ..one import alpha",
                "line_number": 1,
            }
        ]


def _manipulate_data_file(data_file: Path, snippet: str, replacement: str) -> None:
    with open(data_file) as file:
        filedata = file.read()

    filedata = filedata.replace(snippet, replacement)

    with open(data_file, "w") as file:
        file.write(filedata)
