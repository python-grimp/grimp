from __future__ import annotations

import importlib.util
import logging
import os
import sys
from importlib.machinery import ModuleSpec

from grimp import exceptions
from grimp.application.ports.packagefinder import AbstractPackageFinder
from grimp.domain.valueobjects import Module

logger = logging.getLogger(__name__)


class ImportLibPackageFinder(AbstractPackageFinder):
    def determine_package_directories(self, package_name: str) -> set[str]:
        # Attempt to locate the package file.
        spec = importlib.util.find_spec(package_name)
        if not spec:
            logger.debug(f"sys.path: {sys.path}")
            msg = f"Could not find package '{package_name}' in your Python path."
            raise ValueError(msg)

        if (
            spec.has_location
            and spec.origin
            and (not self._is_a_package(spec) or self._has_a_non_namespace_parent(spec))
        ):
            raise exceptions.NotATopLevelModule

        assert spec.submodule_search_locations  # This should be the case if spec.has_location.
        return set(spec.submodule_search_locations)

    def _is_a_package(self, spec: ModuleSpec) -> bool:
        assert spec.origin
        return os.path.basename(spec.origin) == "__init__.py"

    def _has_a_non_namespace_parent(self, spec: ModuleSpec) -> bool:
        module = Module(spec.name)

        if module.root == module:
            # The module has no parent.
            return False

        root_spec = importlib.util.find_spec(module.parent.name)
        assert root_spec
        return root_spec.has_location
