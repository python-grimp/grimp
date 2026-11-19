"""
Use cases handle application logic.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import cast

from grimp import _rustgrimp as rust  # type: ignore[attr-defined]

from ..application.graph import ImportGraph
from .config import settings

DEFAULT_CACHE_DIR = ".grimp_cache"


class NotSupplied:
    pass


def build_graph(
    package_name: str,
    *additional_package_names: str,
    include_external_packages: bool = False,
    exclude_type_checking_imports: bool = False,
    cache_dir: str | type[NotSupplied] | None = NotSupplied,
) -> ImportGraph:
    """
    Build and return an import graph for the supplied package name(s).

    Args:
        package_name: the name of the top level package for which to build the graph.
        additional_package_names: tuple of additional packages to build the graph from.
        include_external_packages: whether to include any external packages in the graph.
        exclude_type_checking_imports: whether to exclude imports made in type checking guards.
        cache_dir: The directory to use for caching the graph.

    Examples:
        # Single package.
        graph = build_graph("mypackage")
        graph = build_graph("mypackage", include_external_packages=True)
        graph = build_graph("mypackage", exclude_type_checking_imports=True)

        # Multiple packages.
        graph = build_graph("mypackage", "anotherpackage", "onemore")
        graph = build_graph(
            "mypackage", "anotherpackage", "onemore", include_external_packages=True,
        )
    """
    package_names = _validate_package_names_are_strings([package_name, *additional_package_names])
    packages = [
        (name, directory)
        for name in package_names
        for directory in settings.PACKAGE_FINDER.determine_package_directories(name)
    ]
    if cache_dir is NotSupplied:
        cache_dir = DEFAULT_CACHE_DIR

    rust_graph, log_records = rust.build_graph(
        packages,
        # Tolerate a non-boolean (Import Linter has been known to pass None).
        include_external_packages=bool(include_external_packages),
        exclude_type_checking_imports=exclude_type_checking_imports,
        cache_dir=cache_dir,
    )
    # Rust can't use Python's logging, so it returns what should be logged.
    for logger_name, level, message in log_records:
        getattr(logging.getLogger(logger_name), level)(message)

    return ImportGraph.from_rustgraph(rust_graph)


def _validate_package_names_are_strings(
    package_names: Sequence[object],
) -> Sequence[str]:
    for name in package_names:
        if not isinstance(name, str):
            msg = f"Package names must be strings, got {name.__class__.__name__}."
            raise TypeError(msg)
    return cast("Sequence[str]", package_names)
