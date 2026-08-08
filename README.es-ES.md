

# SDK de Python para iFlow Search

SDK de Python para la **API de iFlow Search (心流搜索 API)** — búsqueda web, búsqueda de imágenes y obtención de páginas web, que devuelve datos estructurados aptos para el uso de modelos de lenguaje grandes (LLM) y agentes de IA.

El SDK central independiente del framework, el adaptador MCP, el adaptador LangChain, el adaptador CrewAI y el servidor de herramientas OpenAPI se distribuyen desde este repositorio como paquetes hermanos bajo `packages/`.

## Enlaces

- Documentación de la API: <https://platform.iflow.cn/docs/>
- Documentación de la habilidad: <https://platform.iflow.cn/docs/skill>
- Repositorio oficial de la habilidad: <https://github.com/iflow-ai/iflow-skills/tree/main/skills/iflow-search>
- Repositorio del SDK JS: <https://github.com/zhengyanglsun/iflow-search-js>

## Estado

- ✅ SDK central implementado (`packages/iflow-search/`) — publicado en PyPI como `iflow-search==0.1.0`
- ✅ Clientes síncronos y asíncronos
- ✅ Pruebas de humo con API real verificadas para los tres puntos de conexión
- ✅ pytest / ruff / mypy strict / `python -m build` todos en verde
- ✅ Adaptador MCP (`packages/iflow-search-mcp/`) — publicado en PyPI como `iflow-search-mcp==0.1.0`
- ✅ Adaptador LangChain (`packages/iflow-search-langchain/`) — publicado en PyPI como `iflow-search-langchain==0.1.0`
- ✅ Servidor de herramientas OpenAPI (`packages/iflow-search-openapi/`) — publicado en PyPI como `iflow-search-openapi==0.1.0`
- ✅ Adaptador CrewAI (`packages/iflow-search-crewai/`) — publicado en PyPI como `iflow-search-crewai==0.1.0`

## Instalación

```bash
pip install iflow-search
```

Para desarrollo local:

```bash
git clone https://github.com/zhengyanglsun/iflow-search-py.git
cd iflow-search-py/packages/iflow-search
python -m pip install -e ".[dev]"
```

## Configuración

Establezca su clave de API en el entorno del shell:

```bash
export IFLOW_API_KEY="your-api-key"
```

**Seguridad**:

- No incluya las claves de API en los commits.
- No almacene las claves en este README, en las pruebas, en los fixtures, en los registros (logs) o en los archivos `.env`.
- El SDK lee `IFLOW_API_KEY` únicamente desde el entorno del shell — nunca desde un archivo, nunca desde un parámetro de línea de comandos.

## Inicio rápido — síncrono

```python
from iflow_search import IFlowSearchClient

# Reads IFLOW_API_KEY from the environment.
client = IFlowSearchClient()

web = client.web_search(query="latest LLM benchmarks", count=3)
print(web.results[0].title, web.results[0].url)

images = client.image_search(query="great wall of china", count=3)
print(images.images[0].image_url)

page = client.web_fetch(url="https://example.com")
print(page.title)
```

## Inicio rápido — asíncrono

```python
import asyncio
from iflow_search import AsyncIFlowSearchClient

async def main() -> None:
    async with AsyncIFlowSearchClient() as client:
        web = await client.web_search(query="latest LLM benchmarks", count=3)
        print(web.results[0].title, web.results[0].url)

asyncio.run(main())
```

## Funcionalidades

| Método | Punto de conexión | Devuelve |
|---|---|---|
| `web_search(query=..., count=None)` | `POST /api/search/webSearch` | `WebSearchResponse` con `.results: list[WebSearchResult]` |
| `image_search(query=..., count=None)` | `POST /api/search/imageSearch` | `ImageSearchResponse` con `.images: list[ImageResult]` |
| `web_fetch(url=...)` | `POST /api/search/webFetch` | `WebFetchResponse` con `.title`, `.content`, `.from_cache` |

La API de Python utiliza `query` / `count`; el SDK los transforma en la transmisión a `keywords` / `num`. La estructura original de la respuesta siempre se conserva en `response.raw` para los clientes que necesiten campos que el SDK no modeló.

## Cabeceras de atribución

El SDK envía las siguientes cabeceras en cada peticiónrequest:

| Cabecera | Propósito |
|---|---|
| `Authorization` | `Bearer <api_key>` — generado internamente a partir de `IFLOW_API_KEY`; no modificable por el usuario |
| `Content-Type` | `application/json` |
| `Accept` | `application/json` |
| `IFlow-Source` | identificador del adaptador (por defecto `"python"`) |
| `IFlow-Integration` | nombre del paquete (por defecto `"iflow-search"`) |
| `IFlow-Integration-Version` | versión del paquete instalado |
| `User-Agent` | `<integration_name>/<integration_version>` |

El adaptador MCP además emite, cuando el host establece las variables de entorno correspondientes:

- `IFlow-MCP-Client`
- `IFlow-MCP-Client-Version`

**La clave de API nunca se incluye en ninguna cabecera de atribución.** Las cabeceras de atribución existen únicamente para las estadísticas de uso y deben mantenerse libres de credenciales.

## Estructura del repositorio

```
iflow-search-py/
├── docs/design/python-sdk-design.md       ← core design document
├── docs/design/python-mcp-design.md       ← MCP adapter design document
├── docs/design/python-langchain-design.md ← LangChain adapter design document
├── docs/design/python-openapi-design.md   ← OpenAPI adapter design document
├── packages/
│   ├── iflow-search/                      ← core SDK (PyPI: iflow-search)
│   │   ├── src/iflow_search/
│   │   ├── tests/
│   │   ├── scripts/smoke_real_api.py
│   │   ├── pyproject.toml
│   │   ├── README.md                      ← PyPI long_description
│   │   └── LICENSE
│   ├── iflow-search-mcp/                  ← MCP stdio server (PyPI: iflow-search-mcp)
│   │   ├── src/iflow_search_mcp/
│   │   ├── tests/
│   │   ├── scripts/smoke_stdio.py
│   │   ├── pyproject.toml
│   │   ├── README.md                      ← PyPI long_description
│   │   └── LICENSE
│   ├── iflow-search-langchain/            ← LangChain adapter (PyPI: iflow-search-langchain)
│   │   ├── src/iflow_search_langchain/
│   │   ├── tests/
│   │   ├── scripts/smoke_real_api.py
│   │   ├── pyproject.toml
│   │   ├── README.md                      ← PyPI long_description
│   │   └── LICENSE
│   └── iflow-search-openapi/              ← OpenAPI tool server (PyPI: iflow-search-openapi)
│       ├── src/iflow_search_openapi/
│       ├── tests/
│       ├── scripts/smoke_real_api.py
│       ├── pyproject.toml
│       ├── README.md                      ← PyPI long_description
│       └── LICENSE
└── .github/workflows/ci.yml
```

## Comandos de desarrollo

Desde `packages/iflow-search/`:

```bash
python -m pytest -q                    # 103 offline tests
python -m ruff check .                 # lint
python -m mypy src/iflow_search        # strict typecheck
python -m build                        # build sdist + wheel into dist/
```

## Pruebas de humo con API real

Un script separado y opcional prueba los tres puntos de conexión contra la API en vivo:

```bash
cd packages/iflow-search
export IFLOW_API_KEY="your-api-key"
export IFLOW_SMOKE=1
python scripts/smoke_real_api.py
```

El script de pruebas:

- Es **opcional** — sin `IFLOW_SMOKE=1` se niega a llamar a la API en vivo.
- Lee `IFLOW_API_KEY` únicamente desde el entorno — nunca desde el disco.
- Oculta la clave en toda la salida de registros.
- No escribe ningún archivo.

## Adaptadores

### `iflow-search-mcp` — publicado

Servidor stdio MCP para su uso por Claude Code, Claude Desktop, Hermes, OpenCode y otros hosts compatibles con MCP. Expone `iflow_web_search`, `iflow_image_search` e `iflow_web_fetch` como herramientas MCP a través del SDK oficial de Python `mcp`.

```bash
pip install iflow-search-mcp
```

Configure su host MCP para ejecutar el script de consola `iflow-search-mcp`. Ejemplo para el `claude_desktop_config.json` de Claude Desktop:

```json
{
  "mcpServers": {
    "iflow-search": {
      "command": "iflow-search-mcp",
      "env": {
        "IFLOW_API_KEY": "sk-..."
      }
    }
  }
}
```

Variables de entorno reconocidas: `IFLOW_API_KEY` (requerida), `IFLOW_BASE_URL`, `IFLOW_TIMEOUT_MS`, `IFLOW_MCP_CLIENT`, `IFLOW_MCP_CLIENT_VERSION`. El README propio del paquete cubre la configuración por host y los esquemas completos de las herramientas; consulte `docs/design/python-mcp-design.md` para la justificación del diseño.

### `iflow-search-langchain` — publicado

Fábricas `BaseTool` de LangChain para `iflow_web_search`, `iflow_image_search` e `iflow_web_fetch`. LangGraph consume estas herramientas directamente (`create_react_agent`, `ToolNode`), por lo que no existe un paquete `iflow-search-langgraph` separado.

```bash
pip install iflow-search-langchain
```

```python
import os
from iflow_search_langchain import create_iflow_search_tools

tools = create_iflow_search_tools(api_key=os.environ["IFLOW_API_KEY"])
# [iflow_web_search, iflow_image_search, iflow_web_fetch] — wire into your agent.
```

Cada herramienta utiliza `response_format="content_and_artifact"`: `_run` / `_arun` devuelven `(content: str, artifact: dict)`. Los clientes construidos automáticamente llevan la atribución `IFlow-Source: langchain`; los clientes proporcionados por el usuario no se modifican. El README propio del paquete cubre la configuración, la atribución, el ciclo de vida y el ejemplo de LangGraph; consulte `docs/design/python-langchain-design.md` para la justificación del diseño.

### `iflow-search-openapi` — publicado

Servidor de herramientas FastAPI / OpenAPI 3.1 para Open WebUI, Coze y plataformas similares que consumen catálogos de herramientas OpenAPI. Expone `iflow_web_search`, `iflow_image_search` e `iflow_web_fetch` como puntos de conexión `POST /tools/*`; sirve `/openapi.json` y `/health`.

```bash
pip install iflow-search-openapi
export IFLOW_API_KEY="your-api-key"
iflow-search-openapi
```

El enlace por defecto es `127.0.0.1:8787` (solo local). Establezca `IFLOW_OPENAPI_HOST=0.0.0.0` para exposición en LAN o contenedores. Autenticación bearer opcional para usuarios externos mediante `IFLOW_OPENAPI_AUTH_TOKEN`; CORS configurable mediante `IFLOW_OPENAPI_CORS_ORIGIN`. El README propio del paquete cubre la configuración y los flujos de importación por plataforma; consulte `docs/design/python-openapi-design.md` para la justificación del diseño.

Consulte `docs/design/python-sdk-design.md` para la justificación del diseño central.

## Licencia

[MIT](./packages/iflow-search/LICENSE)
