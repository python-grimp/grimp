import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

import pytest

import grimp

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


def test_build_graph_uses_cache(build_graph, copied_cachingpackage):
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


def test_cache_preserves_is_lazy(build_graph):
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


def test_data_file_records_version_and_is_lazy(build_graph, copied_cachingpackage):
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


def test_cache_with_different_version_is_rebuilt(build_graph, copied_cachingpackage, caplog):
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
        if build_graph is grimp.build_graph:  # Only the Python implementation logs.
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


@pytest.mark.parametrize(
    "build_graph_writing_cache, build_graph_reading_cache",
    (
        (grimp.build_graph, grimp.build_graph_rust),
        (grimp.build_graph_rust, grimp.build_graph),
    ),
)
def test_cache_is_shared_between_implementations(
    copied_cachingpackage, build_graph_writing_cache, build_graph_reading_cache
):
    with tempfile.TemporaryDirectory() as cache_dir:
        build_graph_writing_cache("cachingpackage", cache_dir=cache_dir)

        data_file = Path(cache_dir) / "27aa562ad2a4745eb20ecf156430dbfeb0e90610.data.json"
        snippet = "from ..one import alpha"
        replacement = snippet + "  # Inserted by test"
        _manipulate_data_file(data_file, snippet, replacement)

        graph = build_graph_reading_cache("cachingpackage", cache_dir=cache_dir)

        [import_details] = graph.get_import_details(
            importer="cachingpackage.two.alpha", imported="cachingpackage.one.alpha"
        )
        assert import_details["line_contents"] == replacement


def _manipulate_data_file(data_file: Path, snippet: str, replacement: str) -> None:
    with open(data_file) as file:
        filedata = file.read()

    filedata = filedata.replace(snippet, replacement)

    with open(data_file, "w") as file:
        file.write(filedata)


# Tests of the cache's behaviour, using real files.
# ---------------------------------------------------

MYPACKAGE_FILES = {
    "mypackage/__init__.py": "",
    "mypackage/one.py": "from . import two",
    "mypackage/two.py": "from . import three",
    "mypackage/three.py": "",
}
ANOTHERPACKAGE_FILES = {
    "anotherpackage/__init__.py": "",
    "anotherpackage/one.py": "import externalpackage\nfrom . import two",
    "anotherpackage/two.py": "",
}
MARKER = "  # Inserted by test"


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "cache"


def _data_file(cache_dir: Path) -> Path:
    [data_file] = cache_dir.glob("*.data.json")
    return data_file


def _insert_marker_in_cache(cache_dir: Path) -> None:
    """
    Alter the cached line contents of "from . import two", so we can tell if the cache was used.
    """
    _manipulate_data_file(_data_file(cache_dir), "from . import two", "from . import two" + MARKER)


def _line_contents(graph, importer: str, imported: str) -> str:
    [import_details] = graph.get_import_details(importer=importer, imported=imported)
    return import_details["line_contents"]


class TestCacheFiles:
    @pytest.mark.parametrize(
        "include_external_packages, exclude_type_checking_imports, expected_data_file_name",
        (
            # Blake2B 20-character hash of "bluepackage,greenpackage".
            (False, False, "3d0968b3c17583a69a90610a871276fe2110c6f4.data.json"),
            # Blake2B 20-character hash of "bluepackage,greenpackage:external".
            (True, False, "ff83c6ee50a447a433a0c7a345d09de4b0d82a69.data.json"),
            # Blake2B 20-character hash of "bluepackage,greenpackage:no_type_checking".
            (False, True, "5e8b57eaed0aabd7826b5b0cc6cb2b7db8c82fb8.data.json"),
            # Blake2B 20-character hash of "bluepackage,greenpackage:external:no_type_checking".
            (True, True, "91f51d0e59ed9e09cfc3e8a94c9249c4c3ab7184.data.json"),
        ),
    )
    @pytest.mark.parametrize(
        "package_names", (("bluepackage", "greenpackage"), ("greenpackage", "bluepackage"))
    )
    def test_file_names(
        self,
        build_graph,
        write_files,
        cache_dir,
        package_names,
        include_external_packages,
        exclude_type_checking_imports,
        expected_data_file_name,
    ):
        write_files(
            {
                "bluepackage/__init__.py": "",
                "greenpackage/__init__.py": "",
            }
        )

        build_graph(
            *package_names,
            include_external_packages=include_external_packages,
            exclude_type_checking_imports=exclude_type_checking_imports,
            cache_dir=str(cache_dir),
        )

        # There's a meta file per package, and a data file that depends on the packages
        # (but not the order they were passed in) and options.
        assert {path.name for path in cache_dir.iterdir()} == {
            ".gitignore",
            "CACHEDIR.TAG",
            "bluepackage.meta.json",
            "greenpackage.meta.json",
            expected_data_file_name,
        }

    @pytest.mark.parametrize("cache_dir_suffix", ("", "/"))
    @pytest.mark.parametrize(
        "include_external_packages, expected_data_file_name",
        (
            (False, "3d0968b3c17583a69a90610a871276fe2110c6f4.data.json"),
            (True, "ff83c6ee50a447a433a0c7a345d09de4b0d82a69.data.json"),
        ),
    )
    def test_contents(
        self,
        build_graph,
        write_files,
        cache_dir,
        cache_dir_suffix,
        include_external_packages,
        expected_data_file_name,
    ):
        root = write_files(
            {
                "bluepackage/__init__.py": "",
                "bluepackage/one.py": "from . import two\nimport externalpackage",
                "bluepackage/two.py": "",
                "greenpackage/__init__.py": "",
                "greenpackage/one.py": "",
                "greenpackage/two.py": "from . import one",
            }
        )

        build_graph(
            "bluepackage",
            "greenpackage",
            include_external_packages=include_external_packages,
            cache_dir=f"{cache_dir}{cache_dir_suffix}",
        )

        # The meta files contain the mtime of each module.
        for package, module_files in (
            (
                "bluepackage",
                {"bluepackage": "__init__", "bluepackage.one": "one", "bluepackage.two": "two"},
            ),
            (
                "greenpackage",
                {"greenpackage": "__init__", "greenpackage.one": "one", "greenpackage.two": "two"},
            ),
        ):
            assert json.loads((cache_dir / f"{package}.meta.json").read_text()) == {
                module: os.path.getmtime(root / package / f"{file_stem}.py")
                for module, file_stem in module_files.items()
            }

        # The data file contains the imports of each module.
        expected_blue_one_imports = {("bluepackage.two", False, 1, "from . import two")}
        if include_external_packages:
            expected_blue_one_imports.add(("externalpackage", False, 2, "import externalpackage"))
        data = json.loads((cache_dir / expected_data_file_name).read_text())
        assert data["version"] == 2
        assert {
            module: {tuple(imported) for imported in imports}
            for module, imports in data["imports_by_module"].items()
        } == {
            "bluepackage": set(),
            "bluepackage.one": expected_blue_one_imports,
            "bluepackage.two": set(),
            "greenpackage": set(),
            "greenpackage.one": set(),
            "greenpackage.two": {("greenpackage.one", False, 1, "from . import one")},
        }

    def test_default_cache_dir(self, build_graph, write_files, tmp_path, monkeypatch):
        write_files({"bluepackage/__init__.py": ""})
        monkeypatch.chdir(tmp_path)

        build_graph("bluepackage")

        assert (tmp_path / ".grimp_cache" / "bluepackage.meta.json").exists()

    def test_adds_marker_files(self, build_graph, write_files, cache_dir):
        write_files({"bluepackage/__init__.py": ""})

        build_graph("bluepackage", cache_dir=str(cache_dir))

        assert (cache_dir / ".gitignore").read_text() == "# Automatically created by Grimp.\n*"
        assert (cache_dir / "CACHEDIR.TAG").read_text() == (
            "Signature: 8a477f597d28d172789f06886806bc55\n"
            "# This file is a cache directory tag automatically created by Grimp.\n"
            "# For information about cache directory tags see https://bford.info/cachedir/"
        )

    def test_doesnt_overwrite_marker_files(self, build_graph, write_files, cache_dir):
        write_files({"bluepackage/__init__.py": ""})
        cache_dir.mkdir()
        (cache_dir / ".gitignore").write_text("Something else")

        build_graph("bluepackage", cache_dir=str(cache_dir))

        assert (cache_dir / ".gitignore").read_text() == "Something else"


class TestCacheUse:
    def test_uses_cache_for_unmodified_module(self, build_graph, write_files, cache_dir):
        write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        _insert_marker_in_cache(cache_dir)

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        assert _line_contents(graph, "mypackage.one", "mypackage.two") == (
            "from . import two" + MARKER
        )

    def test_ignores_cache_for_module_with_different_mtime(
        self, build_graph, write_files, cache_dir
    ):
        root = write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        _insert_marker_in_cache(cache_dir)
        path = root / "mypackage" / "one.py"
        os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 100))

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        # The modified module isn't read from the cache, but the others are.
        assert _line_contents(graph, "mypackage.one", "mypackage.two") == "from . import two"
        assert _line_contents(graph, "mypackage.two", "mypackage.three") == "from . import three"

    def test_ignores_cache_for_new_module(self, build_graph, write_files, cache_dir):
        write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        write_files({"mypackage/four.py": "from . import one"})

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        assert graph.direct_import_exists(importer="mypackage.four", imported="mypackage.one")

    def test_ignores_cache_for_module_with_no_cached_mtime(
        self, build_graph, write_files, cache_dir
    ):
        write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        _insert_marker_in_cache(cache_dir)
        meta_file = cache_dir / "mypackage.meta.json"
        mtimes = json.loads(meta_file.read_text())
        del mtimes["mypackage.one"]
        meta_file.write_text(json.dumps(mtimes))

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        assert _line_contents(graph, "mypackage.one", "mypackage.two") == "from . import two"

    def test_ignores_cache_for_module_missing_from_data(self, build_graph, write_files, cache_dir):
        write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        data_file = _data_file(cache_dir)
        data = json.loads(data_file.read_text())
        del data["imports_by_module"]["mypackage.one"]
        data_file.write_text(json.dumps(data))

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        assert graph.direct_import_exists(importer="mypackage.one", imported="mypackage.two")

    @pytest.mark.parametrize(
        "serialized_meta",
        (
            "INVALID_JSON",
            '{"mypackage.one": ["wrong", "type"]}',
        ),
    )
    def test_ignores_corrupt_meta_file(self, build_graph, write_files, cache_dir, serialized_meta):
        write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        _insert_marker_in_cache(cache_dir)
        (cache_dir / "mypackage.meta.json").write_text(serialized_meta)

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        assert _line_contents(graph, "mypackage.one", "mypackage.two") == "from . import two"

    @pytest.mark.parametrize(
        "serialized_data",
        (
            "INVALID_JSON",
            '{"version": 2, "imports_by_module": {"mypackage.one": [["wrong", "type"]]}}',
        ),
    )
    def test_ignores_corrupt_data_file(self, build_graph, write_files, cache_dir, serialized_data):
        write_files(MYPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        _data_file(cache_dir).write_text(serialized_data)

        graph = build_graph("mypackage", cache_dir=str(cache_dir))

        assert _line_contents(graph, "mypackage.one", "mypackage.two") == "from . import two"
        # The cache is repaired.
        data = json.loads(_data_file(cache_dir).read_text())
        assert data["imports_by_module"]["mypackage.one"] == [
            ["mypackage.two", False, 1, "from . import two"]
        ]

    @pytest.mark.parametrize(
        "package_names, options",
        (
            (("mypackage", "anotherpackage"), {}),
            (("mypackage",), {"include_external_packages": True}),
            (("mypackage",), {"exclude_type_checking_imports": True}),
        ),
    )
    def test_doesnt_use_cache_for_different_packages_or_options(
        self, build_graph, write_files, cache_dir, package_names, options
    ):
        write_files(MYPACKAGE_FILES | ANOTHERPACKAGE_FILES)
        build_graph("mypackage", cache_dir=str(cache_dir))
        _insert_marker_in_cache(cache_dir)

        graph = build_graph(*package_names, cache_dir=str(cache_dir), **options)

        assert _line_contents(graph, "mypackage.one", "mypackage.two") == "from . import two"

    @pytest.mark.parametrize("include_external_packages", (False, True))
    def test_uses_cache_for_multiple_packages(
        self, build_graph, write_files, cache_dir, include_external_packages
    ):
        write_files(MYPACKAGE_FILES | ANOTHERPACKAGE_FILES)
        kwargs = dict(
            include_external_packages=include_external_packages, cache_dir=str(cache_dir)
        )
        build_graph("mypackage", "anotherpackage", **kwargs)
        _insert_marker_in_cache(cache_dir)

        graph = build_graph("mypackage", "anotherpackage", **kwargs)

        expected_line_contents = "from . import two" + MARKER
        assert _line_contents(graph, "mypackage.one", "mypackage.two") == expected_line_contents
        assert (
            _line_contents(graph, "anotherpackage.one", "anotherpackage.two")
            == expected_line_contents
        )
        expected_imports = {"anotherpackage.two"}
        if include_external_packages:
            expected_imports.add("externalpackage")
        assert graph.find_modules_directly_imported_by("anotherpackage.one") == expected_imports
