# Use Playwright's official image which includes browsers and necessary system libs
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Copy only requirements first to leverage layer cache
COPY requirements.txt /app/requirements.txt

# Install Python deps
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# Copy repo
COPY . /app

# Environment - safe defaults
ENV PLAYWRIGHT_HEADLESS=true
ENV CHI311_DRY_RUN=true

# Expose application port used by mcp_server
EXPOSE 8000

# Default to running the FastMCP HTTP server (mcp_server.py) so the container
# exposes the MCP transport used by ChatGPT connectors. If you prefer to run
# the FastAPI app instead, change the CMD to uvicorn app.main:app.
ENV PORT=8000

# Run the MCP server which exposes the FastMCP HTTP transport at / (and mounts tools)
CMD ["python", "mcp_server.py"]