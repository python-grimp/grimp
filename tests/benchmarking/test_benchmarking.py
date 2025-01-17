import pytest
import json
from pathlib import Path
from grimp.adaptors.graph import ImportGraph
from grimp import PackageDependency, Route
import grimp


@pytest.fixture(scope="module")
def large_graph():
    raw_json = (Path(__file__).parent / "large_graph.json").read_text()
    graph_dict = json.loads(raw_json)
    graph = ImportGraph()

    for importer, importeds in graph_dict.items():
        for imported in importeds:
            graph.add_import(importer=importer, imported=imported)

    return graph


TOP_LEVEL_LAYERS = ("plugins", "application", "domain", "data")
DEEP_PACKAGE = "mypackage.plugins.5634303718.1007553798.8198145119"
DEEP_LAYERS = (
    f"{DEEP_PACKAGE}.application.3242334296.1991886645",
    f"{DEEP_PACKAGE}.application.3242334296.6397984863",
    f"{DEEP_PACKAGE}.application.3242334296.9009030339",
    f"{DEEP_PACKAGE}.application.3242334296.6666171185",
    f"{DEEP_PACKAGE}.application.3242334296.1693068682",
    f"{DEEP_PACKAGE}.application.3242334296.1752284225",
    f"{DEEP_PACKAGE}.application.3242334296.9089085203",
    f"{DEEP_PACKAGE}.application.3242334296.5033127033",
    f"{DEEP_PACKAGE}.application.3242334296.2454157946",
)


def test_build_django_uncached(benchmark):
    """
    Benchmarks building a graph of real package - in this case Django.

    In this benchmark, the cache is turned off.
    """
    fn = lambda: grimp.build_graph("django", cache_dir=None)
    if hasattr(benchmark, "pedantic"):
        # Running with pytest-benchmark
        benchmark.pedantic(fn, rounds=3)
    else:
        # Running with codspeed.
        benchmark(fn)

