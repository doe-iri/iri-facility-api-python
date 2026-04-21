"""Dynamic loading for versioned API routers."""

import importlib
import pkgutil
import re
from dataclasses import dataclass
from types import ModuleType

from fastapi import APIRouter

ROUTER_GROUP_ORDER = (
    "facility",
    "status",
    "account",
    "compute",
    "filesystem",
    "task",
)


@dataclass(frozen=True)
class LoadedRouter:
    """A router loaded from a versioned route group."""

    version: str
    group: str
    router: APIRouter


def version_from_api_url(api_url: str) -> str:
    """Extract the semantic API version from a configured API URL."""
    tail = api_url.rstrip("/").split("/")[-1]
    if re.fullmatch(r"v\d+", tail):
        return tail
    return "v1"


def _version_number(version: str) -> int:
    match = re.fullmatch(r"v(\d+)", version)
    if not match:
        raise ValueError(f"Unsupported API version name: {version}")
    return int(match.group(1))


def _version_packages(max_version: str) -> list[str]:
    package = importlib.import_module("app.routers")
    target = _version_number(max_version)
    versions = []

    for module_info in pkgutil.iter_modules(package.__path__):
        if not module_info.ispkg:
            continue
        if not re.fullmatch(r"v\d+", module_info.name):
            continue
        if _version_number(module_info.name) <= target:
            versions.append(module_info.name)

    return sorted(versions, key=_version_number)


def _group_packages(version_module: ModuleType) -> list[str]:
    discovered = {
        module_info.name
        for module_info in pkgutil.iter_modules(version_module.__path__)
        if module_info.ispkg
    }
    ordered = [group for group in ROUTER_GROUP_ORDER if group in discovered]
    ordered.extend(sorted(discovered - set(ROUTER_GROUP_ORDER)))
    return ordered


def load_routers(max_version: str) -> list[LoadedRouter]:
    """
    Load routers up through max_version.

    Version folders are additive: v1 contains the baseline surface, while later
    versions can provide only new or changed route groups.
    """
    loaded = []

    for version in _version_packages(max_version):
        version_module = importlib.import_module(f"app.routers.{version}")
        for group in _group_packages(version_module):
            route_module = importlib.import_module(f"app.routers.{version}.{group}.{group}")
            router = getattr(route_module, "router", None)
            if router is None:
                continue
            loaded.append(LoadedRouter(version=version, group=group, router=router))

    return loaded
