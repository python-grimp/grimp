import pytest

from grimp import build_graph

# Files are empty unless stated otherwise.
HAPPY_PATH_FILES = {
    "mypackage/__init__.py": "",
    "mypackage/not-a-python-file.txt": "",
    "mypackage/.hidden": "",
    "mypackage/foo/__init__.py": "",
    "mypackage/foo/one.py": "",
    "mypackage/foo/two/__init__.py": "",
    "mypackage/foo/two/green.py": "",
    "mypackage/foo/two/blue.py": "",
}


def test_happy_path(write_files):
    write_files(HAPPY_PATH_FILES)

    graph = build_graph("mypackage", cache_dir=None)

    assert graph.modules == {
        "mypackage",
        "mypackage.foo",
        "mypackage.foo.one",
        "mypackage.foo.two",
        "mypackage.foo.two.green",
        "mypackage.foo.two.blue",
    }


NAMESPACE_FILES = {
    "somenamespace/foo/blue/__init__.py": "",
    "somenamespace/foo/blue/one.py": "",
    "somenamespace/foo/blue/two/__init__.py": "",
    "somenamespace/foo/blue/two/alpha.py": "",
    "somenamespace/foo/blue/noinitpackage/three.py": "",
    "somenamespace/foo/blue/noinitpackage/orphan/__init__.py": "",
    "somenamespace/foo/blue/noinitpackage/orphan/four.py": "",
    "somenamespace/foo/green/five/__init__.py": "",
    "somenamespace/foo/green/five/beta.py": "",
    "somenamespace/foo/non_python_directory/six/README.txt": "",
}
MODULES_FOO_BLUE = {
    "somenamespace.foo.blue",
    "somenamespace.foo.blue.one",
    "somenamespace.foo.blue.two",
    "somenamespace.foo.blue.two.alpha",
}
MODULES_FOO_GREEN_FIVE = {
    "somenamespace.foo.green.five",
    "somenamespace.foo.green.five.beta",
}


@pytest.mark.parametrize(
    "package_name, expected_modules",
    [
        (
            "somenamespace",
            MODULES_FOO_BLUE
            | MODULES_FOO_GREEN_FIVE
            | {"somenamespace", "somenamespace.foo", "somenamespace.foo.green"},
        ),
        (
            "somenamespace.foo",
            MODULES_FOO_BLUE
            | MODULES_FOO_GREEN_FIVE
            | {"somenamespace.foo", "somenamespace.foo.green"},
        ),
        ("somenamespace.foo.blue", MODULES_FOO_BLUE),
    ],
)
def test_namespaced_packages(write_files, package_name, expected_modules):
    write_files(NAMESPACE_FILES)

    graph = build_graph(package_name, cache_dir=None)

    # Note: namespace directories are only included if they (indirectly) contain Python files.
    assert graph.modules == expected_modules


def test_ignores_orphaned_python_files(write_files):
    # Python files in directories that don't contain an __init__.py should not be discovered.
    write_files(
        {
            "mypackage/__init__.py": "",
            "mypackage/two/__init__.py": "",
            "mypackage/two/green.py": "",
            "mypackage/noinitpackage/green.py": "",
            "mypackage/noinitpackage/orphan/__init__.py": "",
            "mypackage/noinitpackage/orphan/red.py": "",
        }
    )

    graph = build_graph("mypackage", cache_dir=None)

    assert graph.modules == {"mypackage", "mypackage.two", "mypackage.two.green"}


def test_ignores_invalid_identifier_directories(write_files):
    write_files(
        {
            f"namespacepackage/{path}": ""
            for path in (
                "foo/valid_underscore_name/__init__.py",
                "foo/valid_underscore_name/mod.py",
                "foo/invalid-hyphenated-name/__init__.py",
                "foo/invalid-hyphenated-name/mod.py",
                "foo/1nvalid-number-prefixed/__init__.py",
                "foo/1nvalid-number-prefixed/mod.py",
                "foo/valid_non_àscii/__init__.py",
                "foo/valid_non_àscii/mod.py",
                "foo/invalid_non_😃scii/__init__.py",
                "foo/invalid_non_😃scii/mod.py",
                "bar/__init__.py",
                "bar/mod.py",
            )
        }
    )

    graph = build_graph("namespacepackage", cache_dir=None)

    assert graph.modules == {
        "namespacepackage",
        "namespacepackage.foo",
        "namespacepackage.foo.valid_underscore_name",
        "namespacepackage.foo.valid_underscore_name.mod",
        "namespacepackage.foo.valid_non_àscii",
        "namespacepackage.foo.valid_non_àscii.mod",
        "namespacepackage.bar",
        "namespacepackage.bar.mod",
    }


@pytest.mark.parametrize("extension", ("py", "txt"))
def test_ignores_dotted_python_files(write_files, extension):
    # Python files containing dots (other than the one before .py) should not be discovered.
    write_files(
        {
            "mypackage/__init__.py": "",
            "mypackage/foo.py": "",
            "mypackage/bar/__init__.py": "",
            f"mypackage/bar/baz.dotted.{extension}": "",
        }
    )

    graph = build_graph("mypackage", cache_dir=None)

    assert graph.modules == {"mypackage", "mypackage.foo", "mypackage.bar"}


def test_ignores_hidden_directories(write_files):
    write_files(
        {
            "mypackage/__init__.py": "",
            "mypackage/two/__init__.py": "",
            "mypackage/two/green.py": "",
            "mypackage/.hidden/green.py": "",
            "mypackage/.hidden/orphan/__init__.py": "",
            "mypackage/.hidden/orphan/red.py": "",
        }
    )

    graph = build_graph("mypackage", cache_dir=None)

    assert graph.modules == {"mypackage", "mypackage.two", "mypackage.two.green"}


def test_follows_symlinked_directories(write_files, tmp_path):
    write_files(
        {
            "mypackage/__init__.py": "",
            "elsewhere/__init__.py": "",
            "elsewhere/green.py": "",
        }
    )
    (tmp_path / "mypackage" / "linked").symlink_to(
        tmp_path / "elsewhere", target_is_directory=True
    )

    graph = build_graph("mypackage", cache_dir=None)

    assert graph.modules == {"mypackage", "mypackage.linked", "mypackage.linked.green"}
