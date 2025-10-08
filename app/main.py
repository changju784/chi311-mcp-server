from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routes import mcp_routes
import os

# Initialize FastAPI app
app = FastAPI(
    title="Chi311 MCP Server",
    description="MCP-compatible API to automate Chicago 311 service requests.",
    version="0.1.0"
)

# Serve .well-known folder for plugin discovery
base_dir = os.path.dirname(os.path.dirname(__file__))
well_known_path = os.path.join(base_dir, ".well-known")
if os.path.exists(well_known_path):
    app.mount("/.well-known", StaticFiles(directory=well_known_path), name="well-known")

# Serve static files (e.g., logo.png)
static_path = os.path.join(base_dir, "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# CORS setup (allow all origins for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your MCP routes
app.include_router(mcp_routes.router, prefix="/mcp", tags=["MCP"])

# Root route
@app.get("/")
def root():
    return {"message": "Chi311 MCP Server running!"}
