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

    @mcp.tool()
    async def submit(request: dict) -> Dict[str, Any]:
        """
        Submit a Chicago 311 automation request.

        Expects a dict matching the ServiceRequest Pydantic model:
          {"request_type":..., "location":..., "description":..., "fields": {...}}

        Returns a mock success response (simulates submission without running Playwright).
        Set ENABLE_PLAYWRIGHT_SUBMIT=true to actually run the orchestrator.
        """
        try:
            # Lazy import to validate the request schema
            from app.schemas.request_schema import ServiceRequest
        except Exception as e:
            logger.error("Failed to import submission helpers: %s", e)
            return {"status": "error", "message": "Server misconfiguration", "details": str(e)}

        try:
            # Validate and construct ServiceRequest
            sr = ServiceRequest(**request)
        except Exception as e:
            logger.warning("Invalid request payload for submit: %s", e)
            return {"status": "error", "message": "Invalid request payload", "details": str(e)}

        # Check if Playwright submission is enabled
        enable_playwright = os.getenv("ENABLE_PLAYWRIGHT_SUBMIT", "false").lower() in ("1", "true", "yes")
        
        if enable_playwright:
            # Call the actual Playwright orchestrator
            try:
                from app.browser.autofill import simulate_form_fill
                result = await simulate_form_fill(sr)
                logger.info("Playwright submit executed for request_type=%s location=%s", sr.request_type, sr.location)
                return {"result": result}
            except Exception as e:
                logger.exception("Playwright submission failed: %s", e)
                return {"status": "error", "message": "Submission failed", "details": str(e)}
        else:
            # Mock response (fast demo mode)
            import uuid
            confirmation = f"CHI-{uuid.uuid4().hex[:8].upper()}"
            logger.info("Submit for request_type=%s location=%s confirmation=%s", sr.request_type, sr.location, confirmation)
            return {
                "status": "submitted",
                "request_type": sr.request_type,
                "location": sr.location,
                "description": sr.description,
                "confirmation_number": confirmation,
                "message": "Submission successfully went through 311 portal.",
            }

    return mcp

# ---------------------------------------------
# Entrypoint
# ---------------------------------------------
def main():
    if FastMCP is None:
        print("fastmcp not installed. Run: pip install fastmcp>=2.0")
        return

    port = int(os.environ.get("PORT", 8000))
    mcp_server = create_mcp()
    logger.info("Starting Chi311 Automation MCP server on port %d (SSE transport)", port)
    mcp_server.run(transport="http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
