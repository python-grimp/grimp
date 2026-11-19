from __future__ import annotations

import abc


class AbstractPackageFinder(abc.ABC):
    @abc.abstractmethod
    def determine_package_directories(self, package_name: str) -> set[str]:
        raise NotImplementedError
