from pathlib import Path

import pytest

from grimp import exceptions


def test_syntax_error_includes_module(build_graph):
    filename = str(
        (
            Path(__file__).parent.parent / "assets" / "syntaxerrorpackage" / "foo" / "one.py"
        ).resolve()
    )

    with pytest.raises(exceptions.SourceSyntaxError) as excinfo:
        build_graph("syntaxerrorpackage", cache_dir=None)

    expected_exception = exceptions.SourceSyntaxError(
        filename=filename, lineno=5, text="fromb . import two"
    )
    assert expected_exception == excinfo.value
