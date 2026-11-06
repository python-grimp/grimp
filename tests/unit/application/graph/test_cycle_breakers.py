import pytest

from grimp.application.graph import ImportGraph
from grimp.exceptions import ModuleNotPresent


def _build_graph_with_no_imports() -> ImportGraph:
    graph = ImportGraph()
    for module in (
        "pkg",
        "pkg.foo",
        "pkg.foo.blue",
        "pkg.foo.blue.one",
        "pkg.foo.blue.two",
        "pkg.foo.green",
        "pkg.bar",
        "pkg.bar.red",
        "pkg.bar.red.three",
        "pkg.bar.red.four",
        "pkg.bar.red.five",
        "pkg.bar.red.six",
        "pkg.bar.red.seven",
        "pkg.bar.yellow",
        "pkg.bar.yellow.eight",
        "pkg.bar.orange",
        "pkg.bar.orange.nine",
        "pkg.bar.orange.nine.alpha",
        "pkg.bar.orange.nine.beta",
        "pkg.bar.orange.ten",
        "pkg.bar.orange.ten.gamma",
        "pkg.bar.orange.ten.delta",
    ):
        graph.add_module(module)
    return graph


def _build_acyclic_graph() -> ImportGraph:
    graph = _build_graph_with_no_imports()
    # Add imports that make:
    #   pkg.foo -> pkg.bar
    #   pkg.bar.yellow -> pkg.foo.red
    #   pkg.bar.orange.nine -> pkg.bar.orange.ten
    for importer, imported in (
        ("pkg.foo", "pkg.bar.red"),
        ("pkg.foo.green", "pkg.bar.yellow"),
        ("pkg.foo.blue.two", "pkg.bar.red.three"),
        ("pkg.foo.blue.two", "pkg.bar.red.four"),
        ("pkg.foo.blue.two", "pkg.bar.red.five"),
        ("pkg.foo.blue.two", "pkg.bar.red.six"),
        ("pkg.foo.blue.two", "pkg.bar.red.seven"),
        ("pkg.bar.yellow", "pkg.bar.red"),
        ("pkg.bar.yellow.eight", "pkg.bar.red.three"),
        ("pkg.bar.yellow.eight", "pkg.bar.red.four"),
        ("pkg.bar.yellow.eight", "pkg.bar.red.five"),
        ("pkg.bar.orange.nine", "pkg.bar.orange.ten.gamma"),
        ("pkg.bar.orange.nine.alpha", "pkg.bar.orange.ten.gamma"),
        ("pkg.bar.orange.nine.beta", "pkg.bar.orange.ten.delta"),
    ):
        graph.add_import(importer=importer, imported=imported)
    return graph


class TestNominateCycleBreakers:
    def test_empty_graph(self):
        graph = ImportGraph()
        graph.add_module("pkg")

        result = graph.nominate_cycle_breakers("pkg")

        assert result == set()

    def test_nonexistent_module(self):
        graph = ImportGraph()
        graph.add_module("pkg")

        with pytest.raises(ModuleNotPresent):
            graph.nominate_cycle_breakers("nonexistent")

    @pytest.mark.parametrize(
        "module",
        (
            "pkg",
            "pkg.foo",
            "pkg.foo.blue",
        ),
    )
    def test_graph_with_no_imports(self, module: str):
        graph = _build_graph_with_no_imports()

        result = graph.nominate_cycle_breakers(module)

        assert result == set()

    @pytest.mark.parametrize(
        "module",
        (
            "pkg",
            "pkg.bar",
            "pkg.foo.blue",
            "pkg.foo.green",  # Leaf package.
        ),
    )
    def test_acyclic_graph(self, module: str):
        graph = _build_acyclic_graph()

        result = graph.nominate_cycle_breakers(module)

        assert result == set()

    def test_one_breaker(self):
        graph = _build_acyclic_graph()
        importer, imported = "pkg.bar.red.four", "pkg.foo.blue.two"
        graph.add_import(importer=importer, imported=imported)
        result = graph.nominate_cycle_breakers("pkg")

        assert result == {(importer, imported)}

    def test_three_breakers(self):
        graph = _build_acyclic_graph()
        imports = {
            ("pkg.bar.red.four", "pkg.foo.blue.two"),
            ("pkg.bar.yellow", "pkg.foo.blue.three"),
            ("pkg.bar", "pkg.foo.blue.three"),
        }
        for importer, imported in imports:
            graph.add_import(importer=importer, imported=imported)

        result = graph.nominate_cycle_breakers("pkg")

        assert result == imports

    def test_nominated_based_on_dependencies_rather_than_imports(self):
        graph = _build_acyclic_graph()
        # Add lots of imports from a single module - this will be treated as
        # a single dependency.
        importer, imported = "pkg.bar.red.four", "pkg.foo.blue.two"
        for i in range(1, 30):
            graph.add_import(
                importer=importer, imported=imported, line_number=i, line_contents="-"
            )

        graph.add_import(importer=importer, imported=imported)

        result = graph.nominate_cycle_breakers("pkg")

        assert result == {(importer, imported)}

    def test_imports_between_passed_package_and_children_are_disregarded(self):
        graph = _build_acyclic_graph()
        parent, child = "pkg.foo.blue", "pkg.foo"
        graph.add_import(importer=parent, imported=child)
        graph.add_import(importer=child, imported=parent)

        result = graph.nominate_cycle_breakers(parent)

        assert result == set()

    def test_on_child_of_root(self):
        graph = _build_acyclic_graph()
        imports = {
            ("pkg.bar.red.five", "pkg.bar.yellow.eight"),
            ("pkg.bar.red", "pkg.bar.yellow"),
        }
        for importer, imported in imports:
            graph.add_import(importer=importer, imported=imported)

        result = graph.nominate_cycle_breakers("pkg.bar")

        assert result == imports

    def test_on_grandchild_of_root(self):
        graph = _build_acyclic_graph()
        imports = {
            ("pkg.bar.orange.ten.gamma", "pkg.bar.orange.nine.alpha"),
            ("pkg.bar.orange.ten", "pkg.bar.orange.nine.alpha"),
        }
        for importer, imported in imports:
            graph.add_import(importer=importer, imported=imported)

        result = graph.nominate_cycle_breakers("pkg.bar.orange")

        assert result == imports

    def test_on_package_with_one_child(self):
        graph = _build_acyclic_graph()
        graph.add_module("pkg.bar.orange.ten.gamma.onechild")

        result = graph.nominate_cycle_breakers("pkg.bar.orange.ten.gamma")

        assert result == set()

    @pytest.mark.parametrize("order", (sorted, reversed))
    def test_tie_breaker_orders_nodes_alphabetically(self, order):
        graph = ImportGraph()
        graph.add_module("pkg")
        # Add a -> b -> c -> d -> e -> a in a loop.
        # We try both orderings to check it's independent of the order
        # in which they're added.
        for importer, imported in order(
            (
                ("a", "b"),
                ("b", "c"),
                ("c", "d"),
                ("d", "e"),
                ("e", "f"),
                ("f", "a"),
            )
        ):
            graph.add_import(importer=f"pkg.{importer}", imported=f"pkg.{imported}")

        result = graph.nominate_cycle_breakers("pkg")

        # The tie-breaker for selecting nodes to order is alphabetical.
        # That means an import from a later item in the alphabet will be selected first.
        assert result == {("pkg.f", "pkg.a")}

    def test_works_with_chains_of_sources_and_sinks(self):
        graph = ImportGraph()
        graph.add_module("pkg")
        for importer, imported in (
            # Sources
            ("a", "b"),
            ("b", "c"),
            ("c", "d"),
            # Cycle
            ("d", "e"),
            ("e", "f"),
            ("f", "d"),
            # Sinks
            ("f", "g"),
            ("g", "h"),
            ("h", "i"),
        ):
            graph.add_import(importer=f"pkg.{importer}", imported=f"pkg.{imported}")

        result = graph.nominate_cycle_breakers("pkg")

        assert result == {("pkg.f", "pkg.d")}


class TestNominateCycleBreakersBetweenMultiplePackages:
    def test_nonexistent_additional_package(self):
        graph = ImportGraph()
        graph.add_module("pkg")
        graph.add_module("pkg.foo")

        with pytest.raises(ModuleNotPresent):
            graph.nominate_cycle_breakers("pkg.foo", "nonexistent")

    def test_overlapping_packages_raise_value_error(self):
        graph = _build_acyclic_graph()

        with pytest.raises(ValueError, match="shared descendants"):
            graph.nominate_cycle_breakers("pkg", "pkg.foo")

    def test_overlapping_packages_raise_value_error_regardless_of_order(self):
        graph = _build_acyclic_graph()

        with pytest.raises(ValueError, match="shared descendants"):
            graph.nominate_cycle_breakers("pkg.foo", "pkg")

    def test_acyclic_between_packages(self):
        graph = _build_acyclic_graph()

        result = graph.nominate_cycle_breakers("pkg.foo", "pkg.bar")

        assert result == set()

    def test_one_breaker_between_sibling_packages(self):
        graph = _build_acyclic_graph()
        # pkg.foo already depends on pkg.bar (via the acyclic fixture).
        # Add an import in the other direction to create a cycle between the two packages.
        importer, imported = "pkg.bar.red.four", "pkg.foo.blue.two"
        graph.add_import(importer=importer, imported=imported)

        result = graph.nominate_cycle_breakers("pkg.foo", "pkg.bar")

        assert result == {(importer, imported)}

    def test_breakers_between_non_sibling_packages(self):
        graph = _build_acyclic_graph()
        # Add a second, unrelated package and create a cycle between it and pkg.foo.
        graph.add_module("other")
        graph.add_module("other.one")
        graph.add_import(importer="pkg.foo.blue.two", imported="other.one")
        graph.add_import(importer="other.one", imported="pkg.foo.blue.one")

        result = graph.nominate_cycle_breakers("pkg.foo", "other")

        # Both edges of the two-node cycle are equally weighted; the tie-breaker
        # (alphabetical by node name, "other" < "pkg.foo") selects the foo -> other edge.
        assert result == {("pkg.foo.blue.two", "other.one")}

    def test_imports_between_packages_treated_as_dependencies(self):
        graph = _build_acyclic_graph()
        importer, imported = "pkg.bar.red.four", "pkg.foo.blue.two"
        for i in range(1, 30):
            graph.add_import(
                importer=importer, imported=imported, line_number=i, line_contents="-"
            )
        graph.add_import(importer=importer, imported=imported)

        result = graph.nominate_cycle_breakers("pkg.foo", "pkg.bar")

        assert result == {(importer, imported)}

    def test_breakers_between_three_packages(self):
        graph = ImportGraph()
        for module in ("pkg", "pkg.a", "pkg.b", "pkg.c"):
            graph.add_module(module)
        # Create a cycle spanning all three packages: a -> b -> c -> a.
        graph.add_import(importer="pkg.a.one", imported="pkg.b.one")
        graph.add_import(importer="pkg.b.one", imported="pkg.c.one")
        graph.add_import(importer="pkg.c.one", imported="pkg.a.one")

        result = graph.nominate_cycle_breakers("pkg.a", "pkg.b", "pkg.c")

        # Breaking the c -> a edge makes the cycle acyclic. This import involves the
        # third package, so it also proves every additional package is processed.
        assert result == {("pkg.c.one", "pkg.a.one")}

    def test_acyclic_when_passing_leaf_packages(self):
        # Passing two childless modules that have only a one-way dependency between them
        # (pkg.bar.yellow.eight -> pkg.bar.red.three, via the acyclic fixture).
        graph = _build_acyclic_graph()

        result = graph.nominate_cycle_breakers("pkg.bar.red.three", "pkg.bar.yellow.eight")

        assert result == set()
