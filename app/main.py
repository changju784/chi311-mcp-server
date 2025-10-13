import os
import asyncio
import json
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse

# Import your existing route modules
from app.routes import mcp_routes, sse_routes, mcp_tools

# ---------------------------------------------------
# Logging setup
# ---------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chi311.mcp")

# ---------------------------------------------------
# Initialize FastAPI app
# ---------------------------------------------------
app = FastAPI(
    title="Chi311 MCP Server",
    description="MCP-compatible API to automate Chicago 311 service requests.",
    version="0.1.0"
)

# ---------------------------------------------------
# Serve .well-known + static files
# ---------------------------------------------------
base_dir = os.path.dirname(os.path.dirname(__file__))

# Serve .well-known (e.g., ai-plugin.json, manifest, MCP tools)
well_known_path = os.path.join(base_dir, ".well-known")
if os.path.exists(well_known_path):
    app.mount("/.well-known", StaticFiles(directory=well_known_path), name="well-known")

# Serve static assets like /static/logo.png
static_path = os.path.join(base_dir, "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# ---------------------------------------------------
# CORS setup (allow all origins for dev)
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# Include existing 311 automation routes
# ---------------------------------------------------
app.include_router(mcp_routes.router, prefix="/mcp", tags=["MCP"])
app.include_router(mcp_tools.router, prefix="/mcp/tools", tags=["MCP-Tools"])
app.include_router(sse_routes.router, tags=["SSE"])

# ---------------------------------------------------
# Root route
# ---------------------------------------------------
@app.get("/")
def root():
    """Basic health check endpoint."""
    return {"message": "Chi311 MCP Server running!"}

# ---------------------------------------------------
# MCP Tools Manifest
# ---------------------------------------------------
@app.get("/.well-known/mcp/tools")
async def mcp_tools_manifest():
    """
    Return the MCP tool manifest so ChatGPT connectors can discover
    what tools (search/fetch) are available on this server.
    """
    try:
        return {
            "tools": [
                {"name": "search", "description": "Search Chi311 automation handlers and form schemas"},
                {"name": "fetch", "description": "Fetch module or form schema by ID"}
            ]
        }
    except Exception as e:
        logger.error("Error generating MCP manifest: %s", e)
        return {"tools": [{"name": "search"}, {"name": "fetch"}]}

# ---------------------------------------------------
# MCP-compatible SSE endpoint (ChatGPT handshake)
# ---------------------------------------------------
@app.post("/sse")
async def mcp_sse_endpoint(request: Request):
    """
    MCP-compatible Server-Sent Events endpoint.
    ChatGPT Connectors open a POST /sse stream here.
    """
    async def ping_stream():
        try:
            while True:
                yield "event: ping\ndata: {}\n\n"
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            return

    return StreamingResponse(ping_stream(), media_type="text/event-stream")

# ---------------------------------------------------
# Entry point for running directly
# ---------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Chi311 MCP Server on port {port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
