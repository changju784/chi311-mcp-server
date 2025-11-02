from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import mcp_routes, sse_routes, mcp_tools
import os
import logging
import json
from fastapi.responses import JSONResponse

logger = logging.getLogger("chi311.mcp")

# ---------------------------------------------------
# Initialize FastAPI app
# ---------------------------------------------------
app = FastAPI(
    title="Chi311 MCP Server",
    description="MCP-compatible API to automate Chicago 311 service requests.",
    version="0.1.0")

# ---------------------------------------------------
# Mount .well-known and static folders (from project root)
# ---------------------------------------------------
# This ensures compatibility for Replit and local
root_dir = os.path.abspath(os.getcwd())
well_known_path = os.path.join(root_dir, ".well-known")
static_path = os.path.join(root_dir, "static")

if os.path.exists(well_known_path):
    app.mount("/.well-known",
              StaticFiles(directory=well_known_path),
              name="well-known")
    logger.info(f"Mounted .well-known at {well_known_path}")
else:
    logger.warning(f".well-known directory not found at {well_known_path}")

if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# ---------------------------------------------------
# CORS setup
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# Include MCP routes (311 automation + SSE)
# ---------------------------------------------------
app.include_router(mcp_routes.router, prefix="/mcp", tags=["MCP"])
app.include_router(sse_routes.router, tags=["SSE"])
app.include_router(mcp_tools.router, prefix="/mcp/tools", tags=["MCP-Tools"])


# ---------------------------------------------------
# Root route
# ---------------------------------------------------
@app.get("/")
def root():
    return {"message": "Chi311 MCP Server running!"}


# ---------------------------------------------------
# MCP tool manifest (ChatGPT discovery)
# ---------------------------------------------------
@app.get("/.well-known/mcp/tools")
async def mcp_tools_manifest():
    return {
        "tools": [{
            "name":
            "search",
            "description":
            "Search Chi311 automation handlers and form schemas"
        }, {
            "name": "fetch",
            "description": "Fetch module or form schema by ID"
        }]
    }


# Provide the MCP manifest at the canonical location expected by connectors
@app.get("/.well-known/mcp.json", include_in_schema=False)
def mcp_manifest():
    # Try to return the static file if present, else return a small generated manifest
    root_dir = os.path.abspath(os.getcwd())
    manifest_path = os.path.join(root_dir, ".well-known", "mcp.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JSONResponse(content=data)
        except Exception:
            # If parse fails, return raw text wrapped as JSON
            with open(manifest_path, "r", encoding="utf-8") as f:
                text = f.read()
            try:
                return JSONResponse(content=json.loads(text))
            except Exception:
                return JSONResponse(content={"raw": text})

    # Fallback minimal manifest
    fallback = {
        "schema_version": "v1",
        "name_for_human": "Chi311 MCP Server",
        "name_for_model": "chi311_mcp",
        "description_for_human": "MCP manifest for Chi311 automation server.",
        "auth": {"type": "none"},
        "tools": [{"id": "search", "method": "POST", "url": "/mcp/tools/search"},
                  {"id": "fetch", "method": "POST", "url": "/mcp/tools/fetch"},
                  {"id": "submit_311_request", "method": "POST", "url": "/mcp/submit_311_request"},
                  {"id": "sse", "method": "GET", "url": "/sse"}]
    }
    return JSONResponse(content=fallback)


# ---------------------------------------------------
# Main entry (for local testing)
# ---------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
