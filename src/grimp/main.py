__all__ = ["build_graph"]

from .adaptors.packagefinder import ImportLibPackageFinder
from .application.config import settings
from .application.usecases import build_graph

settings.configure(
    PACKAGE_FINDER=ImportLibPackageFinder(),
)
