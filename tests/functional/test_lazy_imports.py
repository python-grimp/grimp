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
    # Spot check that one is stored as is_lazy.
    assert [
        {
            "importer": "lazyimports.one",
            "imported": "lazyimports.two",
            "is_lazy": True,
            "line_number": 2,
            "line_contents": "lazy from lazyimports import two",
        }
    ] == graph.get_import_details(importer="lazyimports.one", imported="lazyimports.two")
