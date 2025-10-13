"""
Chi311 Automation MCP Server
----------------------------
Exposes automation handlers and form schemas for ChatGPT Connectors or 311 Agent AI.

Start locally:
    python mcp_server.py

Expose via ngrok (for ChatGPT):
    ngrok http 8001
Then use the HTTPS URL as your MCP endpoint.
"""

import os
import json
import logging
from typing import Dict, List, Any

# ---------------------------------------------
# Logging setup
# ---------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chi311.mcp")

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None
    logger.error("fastmcp not installed. Please add 'fastmcp>=2.0' to requirements.txt.")

# ---------------------------------------------
# Helpers: index and fetch content
# ---------------------------------------------
def index_handlers() -> List[Dict[str, Any]]:
    """Index available automation modules and form schemas."""
    project_root = os.path.dirname(__file__)
    results = []

    # Index python modules under chi311_automation/modules
    modules_dir = os.path.join(project_root, "chi311_automation", "modules")
    if os.path.isdir(modules_dir):
        for fname in os.listdir(modules_dir):
            if fname.endswith(".py") and not fname.startswith("__"):
                module_id = fname[:-3]
                title = f"automation.module.{module_id}"
                url = f"mcp://modules/{module_id}"
                results.append({"id": module_id, "title": title, "url": url, "metadata": {"type": "module"}})

    # Index form schemas
    schemas_path = os.path.join(project_root, "chi311_automation", "data", "form_schemas.json")
    if os.path.exists(schemas_path):
        try:
            with open(schemas_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            for rt in schema.get("request_types", []):
                rid = rt.get("request_id") or rt.get("request_name")
                if not rid:
                    continue
                title = rt.get("request_name", rid)
                url = f"mcp://forms/{rid}"
                results.append({"id": rid, "title": title, "url": url, "metadata": {"type": "form_schema"}})
        except Exception as e:
            logger.warning("Failed to load form_schemas.json: %s", e)

    return results


def fetch_item(item_id: str) -> Dict[str, Any]:
    """Fetch full module or form schema content for a given item id."""
    project_root = os.path.dirname(__file__)

    # Module fetch
    mod_path = os.path.join(project_root, "chi311_automation", "modules", f"{item_id}.py")
    if os.path.exists(mod_path):
        with open(mod_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "id": item_id,
            "title": f"module:{item_id}",
            "text": text,
            "url": f"file://{mod_path}",
            "metadata": {"type": "module"},
        }

    # Form schema fetch
    schema_path = os.path.join(project_root, "chi311_automation", "data", "form_schemas.json")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        for rt in schema.get("request_types", []):
            if rt.get("request_id") == item_id or rt.get("request_name") == item_id:
                return {
                    "id": item_id,
                    "title": rt.get("request_name"),
                    "text": json.dumps(rt, indent=2),
                    "url": rt.get("url", f"mcp://forms/{item_id}"),
                    "metadata": {"type": "form_schema"},
                }

    raise ValueError(f"Item not found: {item_id}")

# ---------------------------------------------
# MCP Server Definition
# ---------------------------------------------
def create_mcp() -> "FastMCP":
    if FastMCP is None:
        raise RuntimeError("fastmcp is not installed. Please install fastmcp>=2.0.")

    mcp = FastMCP(
        name="Chi311 Automation MCP",
        instructions="Expose 311 automation handlers and form schemas to ChatGPT connectors."
    )

    @mcp.tool()
    async def search(query: str = "") -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for modules or form schemas by substring match.
        Returns:
            {"results": [ {"id":..., "title":..., "url":..., "metadata":...}, ... ]}
        """
        items = index_handlers()
        q = (query or "").lower()
        results = [it for it in items if not q or q in it["id"].lower() or q in it["title"].lower()]
        logger.info("Search query '%s' matched %d items", query, len(results))
        return {"results": results}

    @mcp.tool()
    async def fetch(id: str) -> Dict[str, Any]:
        """
        Fetch the full content for a module or form schema by id.
        """
        item = fetch_item(id)
        logger.info("Fetched item: %s", id)
        return item

    return mcp

# ---------------------------------------------
# Entrypoint
# ---------------------------------------------
def main():
    if FastMCP is None:
        print("fastmcp not installed. Run: pip install fastmcp>=2.0")
        return

    port = int(os.environ.get("PORT", 8001))
    mcp_server = create_mcp()
    logger.info("Starting Chi311 Automation MCP server on port %d (SSE transport)", port)
    mcp_server.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
