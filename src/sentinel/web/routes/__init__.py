from fastapi import FastAPI, APIRouter

import importlib
import pkgutil
from types import ModuleType


def register_routes(app: FastAPI) -> None:  # noqa: D401
    """Automatically discover and attach all route files in this package.

    Each module that exposes a top-level ``router`` variable (an instance of
    ``fastapi.APIRouter``) will be imported and registered.
    """

    package_name = __name__

    for mod_info in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        mod_name = mod_info.name

        # Skip private/utility modules (starting with underscore)
        if mod_name.startswith("_"):
            continue

        module: ModuleType = importlib.import_module(f"{package_name}.{mod_name}")
        router = getattr(module, "router", None)

        if isinstance(router, APIRouter):
            app.include_router(router) 
