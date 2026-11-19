"""
Tests of the imports found when building a graph.

(Ported from unit tests of the scanning of imports, which used an in-memory file system.)
"""

import textwrap

import pytest

from grimp import build_graph
from grimp.domain.valueobjects import DirectImport, Module


def _source(code: str) -> str:
    """Dedent code, and drop the leading newline so that line numbers start from 1."""
    return textwrap.dedent(code).lstrip("\n")


def _direct_imports(graph, importer: str) -> set[DirectImport]:
    return {
        DirectImport(
            importer=Module(details["importer"]),
            imported=Module(details["imported"]),
            line_number=details["line_number"],
            line_contents=details["line_contents"],
            is_lazy=details["is_lazy"],
        )
        for imported in graph.find_modules_directly_imported_by(importer)
        for details in graph.get_import_details(importer=importer, imported=imported)
    }


FOO_PACKAGE_PATHS = (
    "foo/__init__.py",
    "foo/one/__init__.py",
    "foo/one/blue.py",
    "foo/one/green.py",
    "foo/two/__init__.py",
    "foo/two/brown.py",
    "foo/two/yellow.py",
    "foo/three.py",
)


def _foo_package_files(contents_by_path: dict[str, str]) -> dict[str, str]:
    """
    Files in the foo package, which are empty unless otherwise specified.
    """
    files = dict.fromkeys(FOO_PACKAGE_PATHS, "")
    files.update({path: _source(contents) for path, contents in contents_by_path.items()})
    return files


@pytest.mark.parametrize(
    "include_external_packages, expected_result",
    (
        (
            False,
            {
                DirectImport(
                    importer=Module("foo.one"),
                    imported=Module("foo.two"),
                    line_number=1,
                    line_contents="import foo.two",
                )
            },
        ),
        (
            True,
            {
                DirectImport(
                    importer=Module("foo.one"),
                    imported=Module("foo.two"),
                    line_number=1,
                    line_contents="import foo.two",
                ),
                DirectImport(
                    importer=Module("foo.one"),
                    imported=Module("externalone"),
                    line_number=2,
                    line_contents="import externalone",
                ),
                DirectImport(
                    importer=Module("foo.one"),
                    imported=Module("externaltwo"),
                    line_number=3,
                    line_contents="import externaltwo.subpackage  # with comment afterwards.",
                ),
            },
        ),
    ),
)
def test_absolute_imports(write_files, include_external_packages, expected_result):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one.py": _source("""
                import foo.two
                import externalone
                import externaltwo.subpackage  # with comment afterwards.
                arbitrary_expression = 1
            """),
            "foo/two.py": "",
        }
    )

    graph = build_graph(
        "foo",
        include_external_packages=include_external_packages,
        cache_dir=None,
    )

    assert _direct_imports(graph, "foo.one") == expected_result


def test_lazy_imports(write_files):
    write_files(
        _foo_package_files(
            {
                "foo/one/blue.py": """
                    # Absolute no-from
                    lazy import foo.two
                    lazy import externalone
                    lazy import externaltwo.subpackage  # with comment afterwards.
                    arbitrary_expression = 1

                    # Absolute from
                    lazy from foo.one import green
                    lazy from foo.two import yellow
                    if t.TYPE_CHECKING:
                        lazy from foo import three
                    lazy from external import one
                    lazy from external.two import blue  # with comment afterwards.

                    # Relative from
                    lazy from . import green
                    lazy from ..two import yellow
                    lazy from .. import three
                """
            }
        )
    )

    graph = build_graph("foo", include_external_packages=True, cache_dir=None)

    assert _direct_imports(graph, "foo.one.blue") == {
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.two"),
            line_number=2,
            line_contents="lazy import foo.two",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("externalone"),
            line_number=3,
            line_contents="lazy import externalone",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("externaltwo"),
            line_number=4,
            line_contents="lazy import externaltwo.subpackage  # with comment afterwards.",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.one.green"),
            line_number=8,
            line_contents="lazy from foo.one import green",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.two.yellow"),
            line_number=9,
            line_contents="lazy from foo.two import yellow",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.three"),
            line_number=11,
            line_contents="lazy from foo import three",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("external"),
            line_number=12,
            line_contents="lazy from external import one",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("external"),
            line_number=13,
            line_contents="lazy from external.two import blue  # with comment afterwards.",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.one.green"),
            line_number=16,
            line_contents="lazy from . import green",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.two.yellow"),
            line_number=17,
            line_contents="lazy from ..two import yellow",
            is_lazy=True,
        ),
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.three"),
            line_number=18,
            line_contents="lazy from .. import three",
            is_lazy=True,
        ),
    }


def test_non_ascii(write_files):
    write_files(
        {
            "mypackage/__init__.py": "",
            "mypackage/blue.py": _source("""
                from ñon_ascii_变 import *
                from . import ñon_ascii_变
                import mypackage.ñon_ascii_变.ラーメン
            """),
            "mypackage/ñon_ascii_变/__init__.py": "",
            "mypackage/ñon_ascii_变/ラーメン.py": "",
        }
    )

    graph = build_graph("mypackage", include_external_packages=True, cache_dir=None)

    assert _direct_imports(graph, "mypackage.blue") == {
        DirectImport(
            importer=Module("mypackage.blue"),
            imported=Module("ñon_ascii_变"),
            line_number=1,
            line_contents="from ñon_ascii_变 import *",
        ),
        DirectImport(
            importer=Module("mypackage.blue"),
            imported=Module("mypackage.ñon_ascii_变"),
            line_number=2,
            line_contents="from . import ñon_ascii_变",
        ),
        DirectImport(
            importer=Module("mypackage.blue"),
            imported=Module("mypackage.ñon_ascii_变.ラーメン"),
            line_number=3,
            line_contents="import mypackage.ñon_ascii_变.ラーメン",
        ),
    }


def test_single_namespace_package_portion(write_files):
    MODULE_ONE = Module("namespace.foo.one")
    MODULE_TWO = Module("namespace.foo.two")
    MODULE_THREE = Module("namespace.foo.three")
    MODULE_FOUR = Module("namespace.foo.four")
    MODULE_BLUE = Module("namespace.foo.two.blue")
    MODULE_ALPHA = Module("namespace.foo.two.green.alpha")
    write_files(
        {
            "namespace/foo/__init__.py": "",
            "namespace/foo/one.py": _source("""
                import namespace.foo.two
                from namespace.foo import three
                from . import four
            """),
            "namespace/foo/two/__init__.py": "",
            "namespace/foo/three.py": "",
            "namespace/foo/four.py": "",
            "namespace/foo/two/green/__init__.py": "",
            "namespace/foo/two/blue.py": "",
            "namespace/foo/two/green/alpha.py": _source("""
                from .. import blue
                from ... import three
            """),
        }
    )

    graph = build_graph("namespace.foo", include_external_packages=True, cache_dir=None)

    assert _direct_imports(graph, MODULE_ONE.name) == {
        DirectImport(
            importer=MODULE_ONE,
            imported=MODULE_TWO,
            line_number=1,
            line_contents="import namespace.foo.two",
        ),
        DirectImport(
            importer=MODULE_ONE,
            imported=MODULE_THREE,
            line_number=2,
            line_contents="from namespace.foo import three",
        ),
        DirectImport(
            importer=MODULE_ONE,
            imported=MODULE_FOUR,
            line_number=3,
            line_contents="from . import four",
        ),
    }
    assert _direct_imports(graph, MODULE_ALPHA.name) == {
        DirectImport(
            importer=MODULE_ALPHA,
            imported=MODULE_BLUE,
            line_number=1,
            line_contents="from .. import blue",
        ),
        DirectImport(
            importer=MODULE_ALPHA,
            imported=MODULE_THREE,
            line_number=2,
            line_contents="from ... import three",
        ),
    }


@pytest.mark.parametrize("include_external_packages", (True, False))
def test_import_of_portion_not_in_graph(write_files, include_external_packages):
    # Include two namespaces, one deeper than the other.
    #
    # Note: unlike the (in-memory) layout this was originally written against, foo.one can't
    # have both a module file and a submodule (blue), so the blue module is namespace.foo.two.blue.
    # It's at the same depth, so its relative imports resolve in the same way.
    MODULE_FOO_ONE = Module("namespace.foo.one")
    MODULE_FOO_BLUE = Module("namespace.foo.two.blue")
    write_files(
        {
            "namespace/foo/__init__.py": "",
            "namespace/foo/one.py": _source("""
                import namespace.bar.one.orange
                from namespace.yellow import one
                from .. import mauve
                if t.TYPE_CHECKING:
                    from ..cyan import one
                from ..magenta.one import alpha
            """),
            "namespace/foo/two/__init__.py": "",
            "namespace/foo/two/blue.py": _source("""
                from ... import teal
                from ...pink import one
                from ...scarlet.one import alpha
            """),
            "namespace/bar/one/green/__init__.py": "",
            "namespace/bar/one/green/alpha.py": "",
        }
    )

    graph = build_graph(
        "namespace.foo",
        "namespace.bar.one.green",
        include_external_packages=include_external_packages,
        cache_dir=None,
    )

    if include_external_packages:
        assert _direct_imports(graph, MODULE_FOO_ONE.name) == {
            DirectImport(
                importer=MODULE_FOO_ONE,
                imported=Module("namespace.bar.one.orange"),
                line_number=1,
                line_contents="import namespace.bar.one.orange",
            ),
            DirectImport(
                importer=MODULE_FOO_ONE,
                imported=Module("namespace.yellow"),
                line_number=2,
                line_contents="from namespace.yellow import one",
            ),
            DirectImport(
                importer=MODULE_FOO_ONE,
                imported=Module("namespace.mauve"),
                line_number=3,
                line_contents="from .. import mauve",
            ),
            DirectImport(
                importer=MODULE_FOO_ONE,
                imported=Module("namespace.cyan"),
                line_number=5,
                line_contents="from ..cyan import one",
            ),
            DirectImport(
                importer=MODULE_FOO_ONE,
                imported=Module("namespace.magenta"),
                line_number=6,
                line_contents="from ..magenta.one import alpha",
            ),
        }
        assert _direct_imports(graph, MODULE_FOO_BLUE.name) == {
            DirectImport(
                importer=MODULE_FOO_BLUE,
                imported=Module("namespace.teal"),
                line_number=1,
                line_contents="from ... import teal",
            ),
            DirectImport(
                importer=MODULE_FOO_BLUE,
                imported=Module("namespace.pink"),
                line_number=2,
                line_contents="from ...pink import one",
            ),
            DirectImport(
                importer=MODULE_FOO_BLUE,
                imported=Module("namespace.scarlet"),
                line_number=3,
                line_contents="from ...scarlet.one import alpha",
            ),
        }
    else:
        assert _direct_imports(graph, MODULE_FOO_ONE.name) == set()
        assert _direct_imports(graph, MODULE_FOO_BLUE.name) == set()


@pytest.mark.parametrize(
    "include_external_packages, expected_result",
    (
        (
            False,
            {
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("foo.one.green"),
                    line_number=1,
                    line_contents="from foo.one import green",
                ),
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("foo.two.yellow"),
                    line_number=2,
                    line_contents="from foo.two import yellow",
                ),
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("foo.three"),
                    line_number=4,
                    line_contents="from foo import three",
                ),
            },
        ),
        (
            True,
            {
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("foo.one.green"),
                    line_number=1,
                    line_contents="from foo.one import green",
                ),
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("foo.two.yellow"),
                    line_number=2,
                    line_contents="from foo.two import yellow",
                ),
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("foo.three"),
                    line_number=4,
                    line_contents="from foo import three",
                ),
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("external"),
                    line_number=5,
                    line_contents="from external import one",
                ),
                DirectImport(
                    importer=Module("foo.one.blue"),
                    imported=Module("external"),
                    line_number=6,
                    line_contents="from external.two import blue  # with comment afterwards.",
                ),
            },
        ),
    ),
)
def test_absolute_from_imports(write_files, include_external_packages, expected_result):
    write_files(
        _foo_package_files(
            {
                "foo/one/blue.py": """
                    from foo.one import green
                    from foo.two import yellow
                    if t.TYPE_CHECKING:
                        from foo import three
                    from external import one
                    from external.two import blue  # with comment afterwards.
                    arbitrary_expression = 1
                """
            }
        )
    )

    graph = build_graph(
        "foo",
        include_external_packages=include_external_packages,
        cache_dir=None,
    )

    assert _direct_imports(graph, "foo.one.blue") == expected_result


@pytest.mark.parametrize("module_to_scan_is_package", (True, False))
def test_relative_from_imports(write_files, module_to_scan_is_package):
    if module_to_scan_is_package:
        module_to_scan = Module("foo.one")
        module_path = "foo/one/__init__.py"
    else:
        module_to_scan = Module("foo.one.blue")
        module_path = "foo/one/blue.py"
    write_files(
        _foo_package_files(
            {
                module_path: """
                    from . import green
                    from ..two import yellow
                    from .. import three
                    arbitrary_expression = 1
                """
            }
        )
    )

    graph = build_graph(
        "foo",
        include_external_packages=False,
        exclude_type_checking_imports=True,
        cache_dir=None,
    )

    assert _direct_imports(graph, module_to_scan.name) == {
        DirectImport(
            importer=module_to_scan,
            imported=Module("foo.one.green"),
            line_number=1,
            line_contents="from . import green",
        ),
        DirectImport(
            importer=module_to_scan,
            imported=Module("foo.two.yellow"),
            line_number=2,
            line_contents="from ..two import yellow",
        ),
        DirectImport(
            importer=module_to_scan,
            imported=Module("foo.three"),
            line_number=3,
            line_contents="from .. import three",
        ),
    }


@pytest.mark.parametrize(
    "import_source",
    ("from .two.yellow import my_function", "from foo.two.yellow import my_function"),
)
def test_trims_to_known_modules(write_files, import_source):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one.py": import_source,
            "foo/two/__init__.py": "",
            "foo/two/yellow.py": "",
        }
    )

    graph = build_graph("foo", include_external_packages=False, cache_dir=None)

    assert _direct_imports(graph, "foo.one") == {
        DirectImport(
            importer=Module("foo.one"),
            imported=Module("foo.two.yellow"),
            line_number=1,
            line_contents=import_source,
        )
    }


def test_trims_to_known_modules_within_init_file(write_files):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one/__init__.py": "from .yellow import my_function",
            "foo/one/yellow.py": "",
            "foo/one/blue/__init__.py": "from .alpha import my_function",
            "foo/one/blue/alpha.py": "",
        }
    )

    graph = build_graph("foo", include_external_packages=False, cache_dir=None)

    assert _direct_imports(graph, "foo.one") == {
        DirectImport(
            importer=Module("foo.one"),
            imported=Module("foo.one.yellow"),
            line_number=1,
            line_contents="from .yellow import my_function",
        )
    }
    assert _direct_imports(graph, "foo.one.blue") == {
        DirectImport(
            importer=Module("foo.one.blue"),
            imported=Module("foo.one.blue.alpha"),
            line_number=1,
            line_contents="from .alpha import my_function",
        )
    }


def test_trims_whitespace_from_start_of_line_contents(write_files):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one.py": _source("""
                def my_function():
                    from . import two
            """),
            "foo/two.py": "",
        }
    )

    graph = build_graph("foo", include_external_packages=False, cache_dir=None)

    assert _direct_imports(graph, "foo.one") == {
        DirectImport(
            importer=Module("foo.one"),
            imported=Module("foo.two"),
            line_number=2,
            line_contents="from . import two",
        ),
    }


@pytest.mark.parametrize(
    "statement, expected_module_name",
    (
        # External packages that share a namespace with an internal module resolve
        # to the shallowest component that does not clash with an internal module namespace.
        ("import namespace", None),
        ("import namespace.foo", None),
        ("from namespace import foo", None),
        ("import namespace.bar", "namespace.bar"),
        ("from namespace import bar", "namespace.bar"),
        ("from ... import bar", "namespace.bar"),
        ("import namespace.bar.orange", "namespace.bar"),
        ("from namespace.bar import orange", "namespace.bar"),
        ("from ...bar import orange", "namespace.bar"),
        ("import namespace.foo.green", "namespace.foo.green"),
        ("from namespace.foo import green", "namespace.foo.green"),
        ("from .. import green", "namespace.foo.green"),
        ("import namespace.foo.green.alpha", "namespace.foo.green"),
        ("from namespace.foo.green import alpha", "namespace.foo.green"),
        ("from ..green import alpha", "namespace.foo.green"),
        ("import namespace.foo.green.alpha.one", "namespace.foo.green"),
        ("from namespace.foo.green.alpha import one", "namespace.foo.green"),
        ("from ..green.alpha import one", "namespace.foo.green"),
    ),
)
def test_external_package_imports_for_namespace_packages(
    write_files, statement, expected_module_name
):
    write_files(
        {
            "namespace/foo/blue/__init__.py": "",
            "namespace/foo/blue/alpha.py": statement,
            "namespace/foo/blue/beta.py": "",
        }
    )

    graph = build_graph("namespace.foo.blue", include_external_packages=True, cache_dir=None)

    module_to_scan = Module("namespace.foo.blue.alpha")
    if expected_module_name:
        assert _direct_imports(graph, module_to_scan.name) == {
            DirectImport(
                importer=module_to_scan,
                imported=Module(expected_module_name),
                line_number=1,
                line_contents=statement,
            ),
        }
    else:
        assert _direct_imports(graph, module_to_scan.name) == set()


@pytest.mark.parametrize("statement", ("import bar.blue", "from bar import blue"))
def test_scans_multiple_packages(write_files, statement):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one.py": _source(f"""
                import foo.two
                {statement}
                import externalone

                arbitrary_expression = 1
            """),
            "foo/two.py": "",
            "bar/__init__.py": "",
            "bar/green.py": "",
            "bar/blue.py": "",
        }
    )

    graph = build_graph("foo", "bar", include_external_packages=False, cache_dir=None)

    assert _direct_imports(graph, "foo.one") == {
        DirectImport(
            importer=Module("foo.one"),
            imported=Module("foo.two"),
            line_number=1,
            line_contents="import foo.two",
        ),
        DirectImport(
            importer=Module("foo.one"),
            imported=Module("bar.blue"),
            line_number=2,
            line_contents=statement,
        ),
    }


@pytest.mark.parametrize("exclude_type_checking_imports", (True, False))
@pytest.mark.parametrize(
    "statement, is_statement_valid",
    (
        ("if t.TYPE_CHECKING:", True),
        ("if TYPE_CHECKING:", True),
        ("if typing.TYPE_CHECKING:", True),
        ("if WEIRD_ALIAS.TYPE_CHECKING:", True),
        ("if type_checking:", False),
        ("while TYPE_CHECKING:", False),
    ),
)
def test_exclude_type_checking_imports(
    write_files, exclude_type_checking_imports, statement, is_statement_valid
):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one.py": _source(f"""
                import foo.two
                {statement}
                    import foo.three
                    import foo.four
                import foo.five
                arbitrary_expression = 1
            """),
            "foo/two.py": "",
            "foo/three.py": "",
            "foo/four.py": "",
            "foo/five.py": "",
        }
    )

    graph = build_graph(
        "foo",
        include_external_packages=False,
        exclude_type_checking_imports=exclude_type_checking_imports,
        cache_dir=None,
    )

    if exclude_type_checking_imports and is_statement_valid:
        expected_result = {
            DirectImport(
                importer=Module("foo.one"),
                imported=Module("foo.two"),
                line_number=1,
                line_contents="import foo.two",
            ),
            DirectImport(
                importer=Module("foo.one"),
                imported=Module("foo.five"),
                line_number=5,
                line_contents="import foo.five",
            ),
        }
    else:
        expected_result = {
            DirectImport(
                importer=Module("foo.one"),
                imported=Module("foo.two"),
                line_number=1,
                line_contents="import foo.two",
            ),
            DirectImport(
                importer=Module("foo.one"),
                imported=Module("foo.three"),
                line_number=3,
                line_contents="import foo.three",
            ),
            DirectImport(
                importer=Module("foo.one"),
                imported=Module("foo.four"),
                line_number=4,
                line_contents="import foo.four",
            ),
            DirectImport(
                importer=Module("foo.one"),
                imported=Module("foo.five"),
                line_number=5,
                line_contents="import foo.five",
            ),
        }
    assert _direct_imports(graph, "foo.one") == expected_result


@pytest.mark.parametrize(
    "code, expected_imported_modules",
    (
        pytest.param(
            """
            if TYPE_CHECKING:
                import foo.two
            else:
                import foo.three
            """,
            {"foo.three"},
            id="else",
        ),
        pytest.param(
            """
            if typing.TYPE_CHECKING:
                import foo.two
            elif sys.version_info >= (3, 12):
                import foo.three
            else:
                import foo.four
            """,
            {"foo.three", "foo.four"},
            id="elif-and-else",
        ),
        pytest.param(
            """
            if sys.version_info >= (3, 12):
                import foo.two
            elif TYPE_CHECKING:
                import foo.three
            else:
                import foo.four
            """,
            {"foo.two", "foo.four"},
            id="elif-type-checking",
        ),
        pytest.param(
            """
            if TYPE_CHECKING:
                if sys.version_info >= (3, 12):
                    import foo.two
                else:
                    import foo.three
                if TYPE_CHECKING:
                    import foo.four
                import foo.five
            """,
            set(),
            id="nested",
        ),
    ),
)
def test_exclude_type_checking_imports_only_excludes_type_checking_branches(
    write_files, code, expected_imported_modules
):
    files = {"foo/__init__.py": ""}
    files.update({f"foo/{name}.py": "" for name in ("two", "three", "four", "five")})
    files["foo/one.py"] = _source(code)
    write_files(files)

    graph = build_graph(
        "foo",
        include_external_packages=False,
        exclude_type_checking_imports=True,
        cache_dir=None,
    )

    imported_modules = {
        direct_import.imported.name for direct_import in _direct_imports(graph, "foo.one")
    }
    assert imported_modules == expected_imported_modules


def test_t_string_syntax(write_files):
    write_files(
        {
            "foo/__init__.py": "",
            "foo/one.py": _source("""
                import foo.two
                # t-strings are only valid in Python 3.14+
                hello = t"Hello"
            """),
            "foo/two.py": "",
        }
    )

    graph = build_graph("foo", include_external_packages=False, cache_dir=None)

    assert _direct_imports(graph, "foo.one") == {
        DirectImport(
            importer=Module("foo.one"),
            imported=Module("foo.two"),
            line_number=1,
            line_contents="import foo.two",
        ),
    }


@pytest.mark.parametrize(
    "import_statement",
    (
        "from namespace.portion.nonexistent import something",
        "from .nonexistent import something",
        "from ..nonexistent import something",
    ),
)
def test_missing_module_in_dotted_root_package_is_ignored(write_files, import_statement: str):
    """
    When a dotted root package (namespace package) contains an import of a missing module
    within that same package, and include_external_packages=True, the Rust code should not
    panic with an index-out-of-bounds error.

    Regression test for https://github.com/python-grimp/grimp/issues/308.
    """
    write_files(
        {
            "namespace/portion/__init__.py": "",
            "namespace/portion/subpackage/__init__.py": "",
            "namespace/portion/subpackage/importer.py": import_statement,
        }
    )

    graph = build_graph("namespace.portion", include_external_packages=True, cache_dir=None)

    assert _direct_imports(graph, "namespace.portion.subpackage.importer") == set()
