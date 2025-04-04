import pytest
import json
import importlib
from pathlib import Path

from tests.config import override_settings
from grimp.adaptors.graph import ImportGraph
from grimp import PackageDependency, Route
import grimp
from copy import deepcopy
from .adaptors import PrefixMissingCache


def _run_benchmark(benchmark, fn, *args, **kwargs):
    return benchmark(fn, *args, **kwargs)


@pytest.fixture(scope="module")
def large_graph():
    raw_json = (Path(__file__).parent / "large_graph.json").read_text()
    graph_dict = json.loads(raw_json)
    graph = ImportGraph()

    for importer, importeds in graph_dict.items():
        graph.add_module(importer)
        for imported in importeds:
            graph.add_import(
                importer=importer,
                imported=imported,
                line_number=1,
                line_contents=f"import {imported}",
            )

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

TOP_LEVEL_PACKAGE_DEPENDENCIES = {
    PackageDependency(
        importer="mypackage.domain",
        imported="mypackage.application",
        routes=frozenset(
            {
                Route(
                    heads=frozenset({"mypackage.domain.7960519247.6215972208"}),
                    middle=(),
                    tails=frozenset(
                        {
                            "mypackage.application.7537183614.6928774480.5676105139.3275676604"  # noqa:E501
                        }
                    ),
                ),
                Route(
                    heads=frozenset(
                        {
                            "mypackage.domain.6928774480.5676105139.1330171288.7588443317.4661445087"  # noqa:E501
                        }
                    ),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.3430454356.1518604543"}),
                ),
                Route(
                    heads=frozenset(
                        {"mypackage.domain.6928774480.5676105139.1262087557.3485088613"}
                    ),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.3430454356.1518604543"}),
                ),
                Route(
                    heads=frozenset({"mypackage.domain.2538372545.1186630948"}),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.8114145747.9320351411"}),
                ),
                Route(
                    heads=frozenset(
                        {
                            "mypackage.domain.6928774480.1028759677.7960519247.2888779155.7486857426"  # noqa:E501
                        }
                    ),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.3430454356.1518604543"}),
                ),
                Route(
                    heads=frozenset({"mypackage.domain.1330171288.2647367251"}),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.4619328254.6682701798"}),
                ),
                Route(
                    heads=frozenset({"mypackage.domain.2538372545.7264406040.9149218450"}),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.2538372545.8114145747"}),
                ),
                Route(
                    heads=frozenset({"mypackage.domain.1330171288.2647367251"}),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.7582995238.6180716911"}),
                ),
                Route(
                    heads=frozenset({"mypackage.domain.1330171288.2647367251"}),
                    middle=(),
                    tails=frozenset({"mypackage.application.7537183614.3851022211.5970652803"}),
                ),
            }
        ),
    ),
    PackageDependency(
        importer="mypackage.domain",
        imported="mypackage.plugins",
        routes=frozenset(
            {
                Route(
                    heads=frozenset({"mypackage.domain.8114145747.6690893472"}),
                    middle=(),
                    tails=frozenset(
                        {"mypackage.plugins.5634303718.6180716911.1810840010.7887344963"}
                    ),
                )
            }
        ),
    ),
    PackageDependency(
        importer="mypackage.application",
        imported="mypackage.plugins",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            "mypackage.application.7537183614.2538372545.1153384736.6297289996",  # noqa:E501
                            "mypackage.application.7537183614.2538372545.1153384736.6404547812.6297289996",  # noqa:E501
                        }
                    ),
                    middle=("mypackage.6398020133.9075581450.6529869526.6297289996",),
                    tails=frozenset(
                        {
                            "mypackage.plugins.5634303718.6180716911.7582995238.1039461003.2943193489",  # noqa:E501
                            "mypackage.plugins.5634303718.6180716911.7582995238.1039461003.6322703811",  # noqa:E501
                        }
                    ),
                )
            }
        ),
    ),
}

DEEP_LAYER_PACKAGE_DEPENDENCIES = {
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.2454157946",
        imported=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        routes=frozenset(
            {
                Route(
                    heads=frozenset({f"{DEEP_PACKAGE}.application.3242334296.2454157946"}),
                    middle=(),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.9089085203"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.5033127033",
        imported=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        routes=frozenset(
            {
                Route(
                    heads=frozenset({f"{DEEP_PACKAGE}.application.3242334296.5033127033"}),
                    middle=(),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.9089085203"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        imported=f"{DEEP_PACKAGE}.application.3242334296.1693068682",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4296536723",
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4641062780",
                        }
                    ),
                    middle=(f"{DEEP_PACKAGE}.application.3242334296",),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.1693068682"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        imported=f"{DEEP_PACKAGE}.application.3242334296.1752284225",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4296536723",
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4641062780",
                        }
                    ),
                    middle=(f"{DEEP_PACKAGE}.application.3242334296",),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.1752284225"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        imported=f"{DEEP_PACKAGE}.application.3242334296.1991886645",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4296536723",
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4641062780",
                        }
                    ),
                    middle=(f"{DEEP_PACKAGE}.application.3242334296",),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.1991886645"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        imported=f"{DEEP_PACKAGE}.application.3242334296.6397984863",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4296536723",
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4641062780",
                        }
                    ),
                    middle=(f"{DEEP_PACKAGE}.application.3242334296",),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.6397984863"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        imported=f"{DEEP_PACKAGE}.application.3242334296.6666171185",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4296536723",
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4641062780",
                        }
                    ),
                    middle=(f"{DEEP_PACKAGE}.application.3242334296",),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.6666171185"}),
                )
            }
        ),
    ),
    PackageDependency(
        importer=f"{DEEP_PACKAGE}.application.3242334296.9089085203",
        imported=f"{DEEP_PACKAGE}.application.3242334296.9009030339",
        routes=frozenset(
            {
                Route(
                    heads=frozenset(
                        {
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4296536723",
                            f"{DEEP_PACKAGE}.application.3242334296.9089085203.4641062780",
                        }
                    ),
                    middle=(f"{DEEP_PACKAGE}.application.3242334296",),
                    tails=frozenset({f"{DEEP_PACKAGE}.application.3242334296.9009030339"}),
                )
            }
        ),
    ),
}


def test_build_django_uncached(benchmark):
    """
    Benchmarks building a graph of real package - in this case Django.

    In this benchmark, the cache is turned off.
    """
    _run_benchmark(benchmark, grimp.build_graph, "django", cache_dir=None)


def test_build_django_from_cache_no_misses(benchmark):
    """
    Benchmarks building a graph of real package - in this case Django.

    This benchmark fully utilizes the cache.
    """
    # Populate the cache first, before beginning the benchmark.
    grimp.build_graph("django")

    _run_benchmark(benchmark, grimp.build_graph, "django")


@pytest.mark.parametrize(
    "number_of_misses",
    (
        2,  # Fewer than the likely number of CPUs.
        15,  # A bit more than the likely number of CPUs.
    ),
)
def test_build_django_from_cache_a_few_misses(benchmark, number_of_misses):
    """
    Benchmarks building a graph of real package - in this case Django.

    This benchmark utilizes the cache except for a few modules, which we add.
    """
    # We must use a special cache class, otherwise the cache will be populated
    # by the first iteration. It would be better to do this using a setup function,
    # which is supported by pytest-benchmark's pedantic mode, but not codspeed.
    # This won't give us a truly accurate picture, but it's better than nothing.

    # Add some specially-named modules which will be treated as not in the cache.
    django_path = Path(importlib.util.find_spec("django").origin).parent
    extra_modules = [
        django_path / f"{PrefixMissingCache.MISSING_PREFIX}{i}.py" for i in range(number_of_misses)
    ]
    for extra_module in extra_modules:
        extra_module.write_text("from django.db import models")

    with override_settings(CACHE_CLASS=PrefixMissingCache):
        # Populate the cache.
        grimp.build_graph("django")

        _run_benchmark(benchmark, grimp.build_graph, "django")

    # Clean up.
    [module.unlink() for module in extra_modules]


class TestFindIllegalDependenciesForLayers:
    @staticmethod
    def _remove_package_dependencies(graph, package_dependencies):
        graph = deepcopy(graph)
        for dep in package_dependencies:
            for route in dep.routes:
                if route.middle:
                    for tail in route.tails:
                        graph.remove_import(importer=route.middle[-1], imported=tail)
                else:
                    for head in route.heads:
                        for tail in route.tails:
                            graph.remove_import(importer=head, imported=tail)
        return graph

    def test_top_level_large_graph_violated(self, large_graph, benchmark):
        result = _run_benchmark(
            benchmark,
            large_graph.find_illegal_dependencies_for_layers,
            layers=TOP_LEVEL_LAYERS,
            containers=("mypackage",),
        )
        assert result == TOP_LEVEL_PACKAGE_DEPENDENCIES

    def test_top_level_large_graph_kept(self, large_graph, benchmark):
        large_graph = self._remove_package_dependencies(
            large_graph, TOP_LEVEL_PACKAGE_DEPENDENCIES
        )
        result = _run_benchmark(
            benchmark,
            large_graph.find_illegal_dependencies_for_layers,
            layers=TOP_LEVEL_LAYERS,
            containers=("mypackage",),
        )
        assert result == set()

    def test_deep_layers_large_graph_violated(self, large_graph, benchmark):
        result = _run_benchmark(
            benchmark, large_graph.find_illegal_dependencies_for_layers, layers=DEEP_LAYERS
        )
        assert result == DEEP_LAYER_PACKAGE_DEPENDENCIES

    def test_deep_layers_large_graph_kept(self, large_graph, benchmark):
        large_graph = self._remove_package_dependencies(
            large_graph, DEEP_LAYER_PACKAGE_DEPENDENCIES
        )
        result = _run_benchmark(
            benchmark, large_graph.find_illegal_dependencies_for_layers, layers=DEEP_LAYERS
        )
        assert result == set()


def test_find_descendants(large_graph, benchmark):
    result = _run_benchmark(benchmark, large_graph.find_descendants, "mypackage")
    assert len(result) == 28222


def test_find_downstream_modules(large_graph, benchmark):
    result = _run_benchmark(
        benchmark, large_graph.find_downstream_modules, DEEP_LAYERS[0], as_package=True
    )
    assert len(result) == 80


def test_find_upstream_modules(large_graph, benchmark):
    result = _run_benchmark(
        benchmark, large_graph.find_upstream_modules, DEEP_LAYERS[0], as_package=True
    )
    assert len(result) == 2159


class TestFindShortestChain:
    def test_chain_found(self, large_graph, benchmark):
        result = _run_benchmark(
            benchmark, large_graph.find_shortest_chain, DEEP_LAYERS[0], DEEP_LAYERS[1]
        )
        assert result is not None

    def test_no_chain(self, large_graph, benchmark):
        result = _run_benchmark(
            benchmark,
            large_graph.find_shortest_chain,
            DEEP_LAYERS[0],
            "mypackage.data.vendors.4053192739.6373932949",
        )
        assert result is None


class TestFindShortestChains:
    def test_chains_found(self, large_graph, benchmark):
        result = _run_benchmark(
            benchmark,
            large_graph.find_shortest_chains,
            DEEP_LAYERS[0],
            DEEP_LAYERS[1],
            as_packages=True,
        )
        assert len(result) > 0

    def test_no_chains(self, large_graph, benchmark):
        result = _run_benchmark(
            benchmark,
            large_graph.find_shortest_chains,
            DEEP_LAYERS[0],
            "mypackage.data.vendors.4053192739.6373932949",
            as_packages=True,
        )
        assert result == set()


def test_copy_graph(large_graph, benchmark):
    _run_benchmark(benchmark, lambda: deepcopy(large_graph))


def test_modules_property_first_access(large_graph, benchmark):
    def f():
        # Benchmarking runs multiple times over the same object, so we need
        # to bust the cache first. The easiest way to do this is to add a module.
        large_graph.add_module("cachebuster")

        # Accessing the modules property is what we're benchmarking.
        _ = large_graph.modules

    _run_benchmark(benchmark, f)


def test_modules_property_many_accesses(large_graph, benchmark):
    def f():
        # Benchmarking runs multiple times over the same object, so we need
        # to bust the cache first. The easiest way to do this is to add a module.
        large_graph.add_module("cachebuster")

        # Accessing the modules property is what we're benchmarking.
        for i in range(1000):
            _ = large_graph.modules

    _run_benchmark(benchmark, f)


def test_get_import_details(benchmark):
    graph = ImportGraph()
    iterations = 100
    for i in range(iterations, 1):
        graph.add_import(
            importer=f"blue_{i}", imported=f"green_{i}", line_contents="...", line_number=i
        )

    def f():
        for i in range(iterations):
            graph.get_import_details(importer=f"blue_{i}", imported=f"green_{i}")

    _run_benchmark(benchmark, f)


def test_find_matching_modules(benchmark, large_graph):
    matching_modules = _run_benchmark(
        benchmark, lambda: large_graph.find_matching_modules("mypackage.domain.**")
    )
    assert len(matching_modules) == 2519


def test_find_matching_direct_imports(benchmark, large_graph):
    matching_imports = _run_benchmark(
        benchmark,
        lambda: large_graph.find_matching_direct_imports(
            "mypackage.domain.** -> mypackage.data.**"
        ),
    )
    assert len(matching_imports) == 4051
