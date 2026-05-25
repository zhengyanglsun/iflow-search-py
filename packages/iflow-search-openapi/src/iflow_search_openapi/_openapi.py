"""Customise FastAPI's generated OpenAPI 3.1 schema (design §7.4).

FastAPI emits a serviceable schema by default. We customise it to:

- Set ``info.title`` and ``info.version`` from the package's own ``__version__``.
- Force the OpenAPI document version to ``3.1.0`` (FastAPI defaults to 3.1 on
  recent versions, but we pin it so consumers can rely on it).
- Add a ``BearerAuth`` security scheme **only** when bearer auth is configured;
  apply it at the top level so every operation inherits it (design §7.4).
- Suppress legacy ``/health`` or ``/openapi.json`` from being decorated with
  bearer security (they should not declare a scheme they're already exempt from
  or always-gated by).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from ._version import __version__


def install_openapi(app: FastAPI, *, bearer_required: bool) -> None:
    def _generate() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(
            title="iFlow Search OpenAPI Tools",
            version=__version__,
            description=(
                "HTTP tool server for the iFlow Search API. Exposes web search, "
                "image search, and web-page fetching as three POST tool endpoints "
                "suitable for OpenAPI tool catalogues (Open WebUI, Coze, ...)."
            ),
            routes=app.routes,
        )
        # Pin OpenAPI version explicitly; future FastAPI releases that change the
        # default would otherwise silently shift what consumers see.
        schema["openapi"] = "3.1.0"

        if bearer_required:
            components = schema.setdefault("components", {})
            security_schemes = components.setdefault("securitySchemes", {})
            security_schemes["BearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
            }
            schema["security"] = [{"BearerAuth": []}]
        else:
            # Explicit empty security stanza is omitted entirely; absence is the
            # idiomatic "no auth required" signal in OpenAPI 3.1.
            schema.pop("security", None)

        app.openapi_schema = schema
        return schema

    app.openapi = _generate  # type: ignore[method-assign]


__all__ = ["install_openapi"]
