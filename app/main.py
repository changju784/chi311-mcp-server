from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import mcp_routes

app = FastAPI(
    title="Chi311 MCP Server",
    description="MCP-compatible API to automate Chicago 311 service requests.",
    version="0.1.0"
)

# Allow all origins for testing (tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mcp_routes.router, prefix="/mcp", tags=["MCP"])

@app.get("/")
def root():
    return {"message": "Chi311 MCP Server running!"}
