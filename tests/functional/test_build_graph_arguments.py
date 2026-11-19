import re

import pytest

from grimp import build_graph


@pytest.mark.parametrize("include_external_packages", (True, False))
def test_happy_path(write_files, include_external_packages):
    write_files(
        {
            "mypackage/__init__.py": "",
            "mypackage/foo/__init__.py": "",
            "mypackage/foo/one.py": "import mypackage.foo.two.green\nfrom .. import Something",
            "mypackage/foo/two/__init__.py": "",
            "mypackage/foo/two/green.py": (
                "import mypackage.foo.two.blue\nfrom external.subpackage import foobar\nimport decimal"
            ),
            "mypackage/foo/two/blue.py": "",
        }
    )

    graph = build_graph(
        "mypackage", include_external_packages=include_external_packages, cache_dir=None
    )

    expected_import_map = {
        "mypackage": set(),
        "mypackage.foo": set(),
        "mypackage.foo.one": {"mypackage.foo.two.green", "mypackage"},
        "mypackage.foo.two": set(),
        "mypackage.foo.two.green": {"mypackage.foo.two.blue"},
        "mypackage.foo.two.blue": set(),
    }
    if include_external_packages:
        expected_import_map["decimal"] = set()
        expected_import_map["external"] = set()
        expected_import_map["mypackage.foo.two.green"] |= {"external", "decimal"}

    assert set(expected_import_map.keys()) == graph.modules
    for importer, imported_modules in expected_import_map.items():
        assert graph.find_modules_directly_imported_by(importer) == imported_modules

    # Check that the external packages are squashed modules.
    if include_external_packages:
        for module in ("external", "decimal"):
            with pytest.raises(
                ValueError, match=re.escape("Cannot find children of a squashed module.")
            ):
                graph.find_children(module)


def test_boolean_additional_package_raises_type_error():
    """
    Tests that a useful error message if build_graph is called
    with a boolean as the second argument.

    This is because earlier versions of build_graph took include_external_packages
    as the second argument, and it's possible it might have been called
    as a positional argument.
    """
    with pytest.raises(TypeError, match=re.escape("Package names must be strings, got bool.")):
        build_graph("mypackage", True)


class TestCacheDir:
    @pytest.fixture(autouse=True)
    def package(self, write_files, tmp_path, monkeypatch):
        write_files({"mypackage/__init__.py": ""})
        # Default caching writes to the current directory.
        monkeypatch.chdir(tmp_path)

    def test_supplied(self, tmp_path):
        build_graph("mypackage", cache_dir=str(tmp_path / "supplied"))

        assert (tmp_path / "supplied" / "mypackage.meta.json").exists()
        assert not (tmp_path / ".grimp_cache").exists()

    def test_not_supplied_uses_default(self, tmp_path):
        build_graph("mypackage")

        assert (tmp_path / ".grimp_cache" / "mypackage.meta.json").exists()

    def test_none_disables_caching(self, tmp_path):
        build_graph("mypackage", cache_dir=None)

        assert not (tmp_path / ".grimp_cache").exists()


def test_forgives_wrong_type_being_passed_to_include_external_packages(write_files):
    write_files(
        {
            "mypackage/__init__.py": "",
            "mypackage/foo/__init__.py": "",
            "mypackage/foo/one.py": "import mypackage.foo.two.green\nfrom .. import Something",
        }
    )

    graph = build_graph(
        "mypackage",
        # Note: this should be a bool, but we want to tolerate it,
        # as Import Linter currently has a bug where it will pass it as None.
        include_external_packages=None,
        cache_dir=None,
    )

    assert graph.modules == {"mypackage", "mypackage.foo", "mypackage.foo.one"}


def test_namespace_package_passed_as_root(write_files):
    # A namespace package can span several directories.
    write_files(
        {
            "mypackage/foo/__init__.py": "",
            "mypackage/foo/one.py": "import mypackage\nfrom . import two",
            "mypackage/foo/two/__init__.py": "",
            "mypackage/foo/two/green.py": "",
            "mypackage/foo/two/blue.py": "",
            "mypackage/bar/__init__.py": "",
            "mypackage/bar/three.py": "",
        },
        root="one",
    )
    write_files(
        {
            "mypackage/foobar/__init__.py": "",
            "mypackage/foobar/four.py": "",
        },
        root="two",
    )

    graph = build_graph("mypackage", cache_dir=None)

    assert graph.modules == {
        "mypackage",
        "mypackage.foo",
        "mypackage.foo.one",
        "mypackage.foo.two",
        "mypackage.foo.two.green",
        "mypackage.foo.two.blue",
        "mypackage.bar",
        "mypackage.bar.three",
        "mypackage.foobar",
        "mypackage.foobar.four",
    }
    assert graph.find_modules_directly_imported_by("mypackage.foo.one") == {
        "mypackage",
        "mypackage.foo.two",
    }
