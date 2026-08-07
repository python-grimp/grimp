import grimp


def test_build_graph_with_lazy_imports():
    """
    Tests we can cope with lazy imports (Python 3.15+).

    Under the hood we use ruff's parser, which understands lazy imports even
    when this is running under a different Python version.
    """
    graph = grimp.build_graph("lazyimports", cache_dir=None)

    result = graph.find_modules_directly_imported_by("lazyimports.one")

    assert {
        "lazyimports.three",
        "lazyimports.two",
        "lazyimports.two.blue",
        "lazyimports.two.green",
    } == result
