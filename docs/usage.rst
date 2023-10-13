=====
Usage
=====

Grimp provides an API in the form of an ``ImportGraph`` that represents all the imports within one or more
top-level Python packages. This object has various methods that make it easy to find out information about
the packages' structures and interdependencies.

Terminology
-----------

The terminology around Python packages and modules can be a little confusing. Here are the definitions we use,
taken in part from `the official Python docs`_:

- **Module**: A file containing Python definitions and statements. This includes ordinary ``.py`` files and
  ``__init__.py`` files.
- **Package**: A Python module which can contain submodules or recursively, subpackages.
- **Top Level Package**: A package that is not a subpackage of another package.
- **Graph**: A graph `in the mathematical sense`_ of a collection of items with relationships between them. Grimp's
  ``ImportGraph`` is a directed graph of imports between modules.
- **Direct Import**: An import from one module to another.
- **Import Chain**: A chain of direct imports between two modules, possibly via other modules. For example, if
  ``mypackage.foo`` imports ``mypackage.bar``, which in turn imports ``mypackage.baz``, then there is an import chain
  between ``mypackage.foo`` and ``mypackage.baz``.
- **Squashed Module**: A module in the graph that represents both itself and all its descendants. Squashed
  modules allow parts of the graph to be simplified. For example, if you include external packages when building
  the graph, each external package will exist in the graph as a single squashed module.

.. _the official Python docs: https://docs.python.org/3/tutorial/modules.html
.. _in the mathematical sense: https://en.wikipedia.org/wiki/Graph_(discrete_mathematics)

Building the graph
------------------

.. code-block:: python

    import grimp

    # Single package
    graph = grimp.build_graph('mypackage')

    # Multiple packages
    graph = grimp.build_graph('mypackage', 'anotherpackage', 'onemore')

    # Include imports of external packages
    graph = grimp.build_graph('mypackage', include_external_packages=True)

    # Exclude imports within a TYPE_CHECKING guard
    graph = grimp.build_graph('mypackage', exclude_type_checking_imports=True)

    # Use a different cache directory, or disable caching altogether
    graph = grimp.build_graph('mypackage', cache_dir="/path/to/cache")
    graph = grimp.build_graph('mypackage', cache_dir=None)

.. py:function:: grimp.build_graph(package_name, *additional_package_names, include_external_packages=False, exclude_type_checking_imports=False)

    Build and return an ImportGraph for the supplied package or packages.

    :param str package_name: The name of an importable package, for example ``'mypackage'``. For regular packages, this
        must be the top level package (i.e. one with no dots in its name). However, in the special case of
        `namespace packages`_, the name of the *portion* should be supplied, for example ``'mynamespace.foo'``.
    :param tuple[str, ...] additional_package_names: Tuple of any additional package names. These can be
        supplied as positional arguments, as in the example above.
    :param bool, optional include_external_packages: Whether to include external packages in the import graph. If this is ``True``,
        any other top level packages (including packages in the standard library) that are imported by this package will
        be included in the graph as squashed modules (see `Terminology`_ above).

        The behaviour is more complex if one of the internal packages is a `namespace portion`_.
        In this case, the squashed module will have the shallowest name that doesn't clash with any internal modules.
        For example, in a graph with internal packages ``namespace.foo`` and ``namespace.bar.one.green``,
        ``namespace.bar.one.orange.alpha`` would be added to the graph as ``namespace.bar.one.orange``. However, in a graph
        with only ``namespace.foo`` as an internal package, the same external module would be added as
        ``namespace.bar``.

        *Note: external packages are only analysed as modules that are imported; any imports they make themselves will
        not be included in the graph.*
    :param bool, optional exclude_type_checking_imports: Whether to exclude imports made in type checking guards. If this is ``True``,
        any import made under an ``if TYPE_CHECKING:`` statement will not be added to the graph.
        See the `typing module documentation`_ for reference. (The type checking guard is detected purely by looking for
        a statement in the form ``if TYPE_CHECKING`` or ``if {some_alias}.TYPE_CHECKING``. It does not check whether
        ``TYPE_CHECKING`` is actually the attribute from the ``typing`` module.)
    :param str, optional cache_dir: The directory to use for caching the graph. Defaults to ``.grimp_cache``. To disable caching,
        pass ``None``. See :doc:`caching`.
    :return: An import graph that you can use to analyse the package.
    :rtype: ImportGraph

.. _typing module documentation: https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING

Methods for analysing the module tree
-------------------------------------

.. py:attribute:: ImportGraph.modules

   All the modules contained in the graph.

    :return: Set of module names.
    :rtype: A set of strings.

.. py:function:: ImportGraph.find_children(module)

   Return all the immediate children of the module, i.e. the modules that have a dotted module name that is one
   level below.

    :param str module: The importable name of a module in the graph, e.g. ``'mypackage'`` or
        ``'mypackage.foo.one'``. This may be any non-squashed module. It doesn't need to be a package itself,
        though if it isn't, it will have no children.
    :return: Set of module names.
    :rtype: A set of strings.
    :raises: ``ValueError`` if the module is a squashed module, as by definition it represents both itself and all
      of its descendants.

.. py:function:: ImportGraph.find_descendants(module)

   Return all the descendants of the module, i.e. the modules that have a dotted module name that is below
   the supplied module, to any depth.

    :param str module: The importable name of the module, e.g. ``'mypackage'`` or ``'mypackage.foo.one'``. As with
      ``find_children``, this doesn't have to be a package, though if it isn't then the set will be empty.
    :return: Set of module names.
    :rtype: A set of strings.
    :raises: ``ValueError`` if the module is a squashed module, as by definition it represents both itself and all
      of its descendants.

Methods for analysing direct imports
------------------------------------

.. py:function:: ImportGraph.direct_import_exists(importer, imported, as_packages=False)

    :param str importer: A module name.
    :param str imported: A module name.
    :param bool as_packages: Whether or not to treat the supplied modules as individual modules, or as entire
        packages (including any descendants).
    :return: Whether or not the importer directly imports the imported module.
    :rtype: ``True`` or ``False``.

.. py:function:: ImportGraph.find_modules_directly_imported_by(module)

    :param str module: A module name.
    :return: Set of all modules in the graph are imported by the supplied module.
    :rtype: A set of strings.

.. py:function:: ImportGraph.find_modules_that_directly_import(module)

    :param str module: A module name.
    :return: Set of all modules in the graph that directly import the supplied module.
    :rtype: A set of strings.

.. py:function:: ImportGraph.get_import_details(importer, imported)

    Provides a way of seeing any available metadata about direct imports between two modules. Usually
    the list will consist of a single dictionary, but it is possible for a module to import another
    module more than once.

    This method should not be used to determine whether an import is present:
    some of the imports in the graph may have no available metadata. For example, if an import
    has been added by the ``add_import`` method without the ``line_number`` and ``line_contents`` specified, then
    calling this method on the import will return an empty list. If you want to know whether the import is present,
    use ``direct_import_exists``.

    The details returned are in the following form::

        [
            {
                'importer': 'mypackage.importer',
                'imported': 'mypackage.imported',
                'line_number': 5,
                'line_contents': 'from mypackage import imported',
            },
            # (additional imports here)
        ]

    If no such import exists, or if there are no available details, an empty list will be returned.

    :param str importer: A module name.
    :param str imported: A module name.
    :return: A list of any available metadata for imports between two modules.
    :rtype: List of dictionaries with the structure shown above. If you want to use type annotations, you may use the
        ``grimp.DetailedImport`` TypedDict for each dictionary.

.. py:function:: ImportGraph.count_imports()

    :return: The number of direct imports in the graph.
    :rtype: Integer.

Methods for analysing import chains
-----------------------------------

.. py:function:: ImportGraph.find_downstream_modules(module, as_package=False)

    :param str module: A module name.
    :param bool as_package: Whether or not to treat the supplied module as an individual module,
                           or as an entire package (including any descendants). If
                           treating it as a package, the result will include downstream
                           modules *external* to the supplied module, and won't include modules within it.
    :return: All the modules that import (even indirectly) the supplied module.
    :rtype: A set of strings.

    Examples::

        # Returns the modules downstream of mypackage.foo.
        graph.find_downstream_modules('mypackage.foo')

        # Returns the modules downstream of mypackage.foo, mypackage.foo.one and
        # mypackage.foo.two.
        graph.find_downstream_modules('mypackage.foo', as_package=True)

.. py:function:: ImportGraph.find_upstream_modules(module, as_package=False)

    :param str module: A module name.
    :param bool as_package: Whether or not to treat the supplied module as an individual module,
                           or as a package (i.e. including any descendants, if there are any). If
                           treating it as a subpackage, the result will include upstream
                           modules *external* to the package, and won't include modules within it.
    :return: All the modules that are imported (even indirectly) by the supplied module.
    :rtype: A set of strings.

.. py:function:: ImportGraph.find_shortest_chain(importer, imported)

    :param str importer: The module at the start of a potential chain of imports between ``importer`` and ``imported``
        (i.e. the module that potentially imports ``imported``, even indirectly).
    :param str imported: The module at the end of the potential chain of imports.
    :return: The shortest chain of imports between the supplied modules, or None if no chain exists.
    :rtype: A tuple of strings, ordered from importer to imported modules, or None.

.. py:function:: ImportGraph.find_shortest_chains(importer, imported)

    :param str importer: A module or subpackage within the graph.
    :param str imported: Another module or subpackage within the graph.
    :return: The shortest import chains that exist between the ``importer`` and ``imported``, and between any modules
             contained within them. Only one chain per upstream/downstream pair will be included. Any chains that are
             contained within other chains in the result set will be excluded.
    :rtype: A set of tuples of strings. Each tuple is ordered from importer to imported modules.

.. py:function:: ImportGraph.chain_exists(importer, imported, as_packages=False)

    :param str importer: The module at the start of the potential chain of imports (as in ``find_shortest_chain``).
    :param str imported: The module at the end of the potential chain of imports (as in ``find_shortest_chain``).
    :param bool as_packages: Whether to treat the supplied modules as individual modules,
         or as packages (including any descendants, if there are any). If
         treating them as packages, all descendants of ``importer`` and
         ``imported`` will be checked too.
    :return:  Return whether any chain of imports exists between ``importer`` and ``imported``,
        even indirectly; in other words, does ``importer`` depend on ``imported``?
    :rtype: bool

Higher level analysis
---------------------

.. py:function:: ImportGraph.find_illegal_dependencies_for_layers(layers, containers=None)

    Find dependencies that don't conform to the supplied layered architecture.

    'Layers' is a software architecture pattern in which a list of sibling modules/packages have a dependency direction
    from high to low. In other words, a higher layer would be allowed to import a lower layer, but not the other way
    around.

    Additionally, multiple layers can be grouped together at the same level; for example ``mypackage.utils`` and
    ``mypackage.logging`` might sit at the bottom, so they cannot import from any other layers. Layers at the same level
    must be *independent*: any dependencies in either direction are treated as illegal.

    Note: each returned :class:`.PackageDependency` does not include all possible illegal :class:`.Route` objects.
    Instead, once an illegal :class:`.Route` is found, the algorithm will temporarily remove it from the graph before continuing
    with its search. As a result, any illegal Routes that have sections in common with other illegal Routes may not
    be returned.

    Additionally, unfortunately the Routes included in the PackageDependencies are not, currently, completely
    deterministic. If there are multiple illegal Routes of the same length, it is not predictable which one will be
    found first. This means that the PackageDependencies returned can vary for the same graph.

    Example::

        dependencies = graph.find_illegal_dependencies_for_layers(
            layers=(
                "mypackage.high",
                "mypackage.medium",
                "mypackage.low",
            ),
        )

    Example with sibling layers::

        dependencies = graph.find_illegal_dependencies_for_layers(
            layers=(
                "red",
                {"green", "blue"},  # Green and blue should be independent.
                "yellow",
            ),
        )

    Example with containers::

        dependencies = graph.find_illegal_dependencies_for_layers(
            layers=(
                "high",
                "medium",
                "low",
            ),
            containers={
                "mypackage.foo",
                "mypackage.bar",
            },
        )

    :param Sequence[str | set[str]] layers: A sequence, each element of which consists either of the name of a layer
        module, or a set of sibling layers that at the same level. If ``containers`` are also specified,
        then these names must be relative to the container. The order is from higher to lower level layers.
        *Any layers that don't exist in the graph will be ignored.*
    :param set[str] containers: The parent modules of the layers, as absolute names that you could
        import, such as ``mypackage.foo``. (Optional.)
    :return: The illegal dependencies in the form of a set of :class:`.PackageDependency` objects. Each package
             dependency is for a different permutation of two layers for which there is a violation, and contains
             information about the illegal chains of imports from the lower layer (the 'importer') to the higher layer
             (the 'imported').
    :rtype: ``set[PackageDependency]``.
    :raises grimp.exceptions.NoSuchContainer: if a container is not a module in the graph.

    .. class:: PackageDependency

      A collection of import dependencies from one Python package to another.

      .. attribute:: importer

        ``str``: The full name of the package within which all the routes start; the downstream package.
           E.g. "mypackage.foo".

      .. attribute:: imported

        ``str``: The full name of the package within which all the routes end; the upstream package.
            E.g. "mypackage.bar".

      .. attribute:: routes

        ``frozenset[grimp.Route]``: A set of :class:`.Route` objects from importer to imported.

    .. class:: Route

      A set of import chains that share the same middle.

      The route fans in at the head and out at the tail, but the middle of the chain just links
      individual modules.

      Example: the following Route represents a chain of imports from
      ``mypackage.orange -> mypackage.utils -> mypackage.helpers -> mypackage.green``, plus an import from
      ``mypackage.red`` to ``mypackage.utils``, and an import from ``mypackage.helpers`` to ``mypackage.blue``::

        Route(
            heads=frozenset(
                {
                    "mypackage.orange",
                    "mypackage.red",
                }
            ),
            middle=(
                "mypackage.utils",
                "mypackage.helpers",
            ),
            tails=frozenset(
                {
                    "mypackage.green",
                    "mypackage.blue",
                }
            ),
        )

    .. attribute:: heads

        ``frozenset[str]``: The importer modules at the start of the chain.

    .. attribute:: middle

        ``tuple[str]``: A sequence of imports that link the head modules to the tail modules.

    .. attribute:: tails

        ``frozenset[str]``:  Imported modules at the end of the chain.

Methods for manipulating the graph
----------------------------------

.. py:function:: ImportGraph.add_module(module, is_squashed=False)

    Add a module to the graph.

    :param str module: The name of a module, for example ``'mypackage.foo'``.
    :param bool is_squashed: If True, the module should be treated as a 'squashed module' (see `Terminology`_ above).
    :return: None

.. py:function:: ImportGraph.remove_module(module)

    Remove a module from the graph.

    If the module is not present in the graph, no exception will be raised.

    :param str module: The name of a module, for example ``'mypackage.foo'``.
    :return: None

.. py:function:: ImportGraph.add_import(importer, imported, line_number=None, line_contents=None)

    Add a direct import between two modules to the graph. If the modules are not already
    present, they will be added to the graph.

    :param str importer: The name of the module that is importing the other module.
    :param str imported: The name of the module being imported.
    :param int line_number: The line number of the import statement in the module.
    :param str line_contents: The line that contains the import statement.
    :return: None

.. py:function:: ImportGraph.remove_import(importer, imported)

    Remove a direct import between two modules. Does not remove the modules themselves.

    :param str importer: The name of the module that is importing the other module.
    :param str imported: The name of the module being imported.
    :return: None

.. py:function:: ImportGraph.squash_module(module)

    'Squash' a module in the graph (see `Terminology`_ above).

    Squashing a pre-existing module will cause all imports to and from the descendants of that module to instead
    point directly at the module being squashed. The import details (i.e. line numbers and contents) will be lost
    for those imports. The descendants will then be removed from the graph.

    :param str module: The name of a module, for example ``'mypackage.foo'``.
    :return: None

.. py:function:: ImportGraph.is_module_squashed(module)

    Return whether a module present in the graph is 'squashed' (see `Terminology`_ above).

    :param str module: The name of a module, for example ``'mypackage.foo'``.
    :return: bool

.. _namespace packages: https://docs.python.org/3/glossary.html#term-namespace-package
.. _namespace portion: https://docs.python.org/3/glossary.html#term-portion