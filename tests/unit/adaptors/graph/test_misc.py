import pytest  # type: ignore

from grimp.adaptors.graph import ImportGraph
from grimp.exceptions import ModuleNotPresent


def test_modules_when_empty():
    graph = ImportGraph()
    assert graph.modules == set()


class TestIsModuleSquashed:
    def test_returns_true_for_module_added_with_is_squashed(self):
        graph = ImportGraph()
        graph.add_module("foo", is_squashed=True)

        assert graph.is_module_squashed("foo")

    def test_returns_false_for_module_added_without_is_squashed(self):
        graph = ImportGraph()
        graph.add_module("foo", is_squashed=False)

        assert not graph.is_module_squashed("foo")

    def test_raises_module_not_present_for_nonexistent_module(self):
        graph = ImportGraph()

        with pytest.raises(ModuleNotPresent):
            assert not graph.is_module_squashed("foo")


class TestFindAllSimpleChains:
    def test_removed_exception(self):
        with pytest.raises(
            AttributeError,
            match="This method has been removed. Consider using find_shortest_chains instead?",
        ):
            ImportGraph().find_all_simple_chains(importer="foo", imported="bar")
