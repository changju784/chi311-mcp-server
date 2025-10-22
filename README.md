<img width="400" height="400" alt="logo" src="https://github.com/user-attachments/assets/4f2279ce-0e97-4bf1-9e46-c502b7aa7484" />

# Chi311 MCP Server

Chi311 Agent is an MCP-compatible server that exposes automation tools for filing non-emergency 311 service requests in the City of Chicago. It combines a FastAPI-hosted API surface with Playwright-based automation modules so an LLM (for example ChatGPT or Anthropic Claude) can discover tools, fetch schemas, and drive automated form submissions.

Quick context: Chi311 (City of Chicago 311) provides a public web portal to submit non-emergency service requests (potholes, graffiti, noise complaints, broken street lights, etc.). This repo aims to make those request types automatable by exposing structured schemas and browser automation handlers to an LLM via the Model Context Protocol (MCP) and a small plugin surface.
(https://311.chicago.gov/s/?language=en_US)

Contents of this README
- Overview
- Architecture (what each top-level module does)
- Quick start (run locally)
- Expose to LLMs (ngrok + plugin manifest)
- Endpoints and tools (what you can call)
- Safety, configuration, and next steps

## Architecture (high level)

- `app/` — FastAPI application and MCP HTTP endpoints
	- `app/main.py` — FastAPI entrypoint, mounts `.well-known` and `static`, registers routes
	- `app/routes/mcp_routes.py` — `/mcp/submit_311_request` (automation trigger)
	- `app/routes/mcp_tools.py` — MCP-style HTTP wrappers: `/mcp/tools/search` and `/mcp/tools/fetch`
	- `app/routes/sse_routes.py` — Server-Sent Events support (`GET /sse`, `POST /sse` broadcast)
	- `app/browser/autofill.py` — Playwright orchestration entrypoint used by the submit route

- `chi311_automation/` — automation pieces (Playwright-based)
	- `chi311_automation/modules/` — handler classes: `address_handler.py`, `form_handler.py`, `contact_handler.py`, `base_handler.py`, `config.py`
	- `chi311_automation/data/form_schemas.json` — pre-extracted form metadata per request type (field selectors, interaction methods, etc.)
	- `chi311_automation/scripts/` — helper scripts and analyzers

- `mcp_server.py` — a simple MCP indexer/fetcher (used for search/fetch logic). The repo also wraps that logic in HTTP endpoints so the MCP tools are available from the same FastAPI process.
 - `mcp_server_local.py` — an alternate local MCP entrypoint tailored for stdio-based connectors (Claude Desktop). It exposes tools like `list_request_types`, `describe_request_type`, and `submit_311_request` and is intended to run locally for interactive desktop LLM integrations.

- `.well-known/` — plugin discovery files (`ai-plugin.json`, `openapi.json`) so ChatGPT can install the plugin (dev mode)

## What this repo exposes to an LLM

- `/mcp/tools/search` (POST) — search available automation tools and form schemas (returns MCP-style content)
- `/mcp/tools/fetch` (POST) — fetch full module source or form schema by id (returns MCP-style content)
- `/mcp/submit_311_request` (POST) — trigger the automation orchestration (Playwright); conservative by default (dry-run)
- `GET /sse` — Server-Sent Events stream to receive asynchronous messages
- `POST /sse` — broadcast JSON payloads to connected SSE clients

These endpoints are served from the same FastAPI process so you can expose a single public URL (via ngrok or similar) for LLM discovery and use.

## Quick start (local development)

Prerequisites
- Python 3.12+
- Git (repo already present)

Steps (Windows PowerShell)

1) Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2) Install Python dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
# if you will run Playwright automation, install browsers:
python -m playwright install
```

3) Start the FastAPI app (serves API, MCP tools and SSE)

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4) (Optional) Start the MCP server script (if you want FastMCP separately)

```powershell
python mcp_server.py
```

## Expose to an LLM (ngrok + plugin discovery)

1) Start the app on port 8000 (see above).
2) Expose it with ngrok (or Cloudflare Tunnel). Example:

```powershell
ngrok http 8000
```

3) Copy the public HTTPS URL (e.g. `https://abcd-1234.ngrok.io`).
4) In ChatGPT (Developer/Plugins), add a custom connector or install the plugin using the manifest URL:

```
https://<your-ngrok-host>/.well-known/ai-plugin.json
```

This plugin manifest and `.well-known/openapi.json` will allow ChatGPT to discover the API. Because the FastAPI app serves MCP tool HTTP endpoints at the same host, both discovery and tool use will route through the same tunnel.

## MCP tool usage (examples)

Search (returns MCP content envelope)

```bash
curl -s -X POST https://<your-host>/mcp/tools/search -H "Content-Type: application/json" -d '{"query":"pothole"}' | jq
```

Fetch (returns full module source or form schema)

```bash
curl -s -X POST https://<your-host>/mcp/tools/fetch -H "Content-Type: application/json" -d '{"id":"address_handler"}' | jq
```

Trigger automation (dry-run by default)

```bash
curl -s -X POST https://<your-host>/mcp/submit_311_request -H "Content-Type: application/json" -d '{"request_type":"aircraft_noise_complaint","location":"200 S Wacker St, Chicago, IL","description":"Example"}' | jq
```

SSE (subscribe)

```bash
curl -N https://<your-host>/sse
# in another terminal, broadcast an event
curl -X POST https://<your-host>/sse -H "Content-Type: application/json" -d '{"event":"test","text":"hello"}'
```

## Configuration and environment variables

- `PLAYWRIGHT_HEADLESS` (true/false) — controls Playwright headless mode
- `CHI311_DRY_RUN` (true/false) — default true; when true the orchestrator will not submit the form
- `CHI311_FULL_SUBMIT` (true/false) — enable only after careful testing to perform real submissions
- `CHI311_FORM_URL` — override the target CHI311 entry URL used by the orchestrator
- `MCP_API_KEY` (optional) — you may add API key protection (recommended) for fetch/broadcast endpoints

Set these in PowerShell before running uvicorn:

```powershell
$env:CHI311_DRY_RUN='true'
$env:PLAYWRIGHT_HEADLESS='true'
```

## Security and safety notes

- By default the orchestration runs in dry-run mode and returns a simulated confirmation. Do not set `CHI311_FULL_SUBMIT=true` until you have thoroughly tested automation flows and added rate limiting and logging.
- The `.well-known/ai-plugin.json` and fetch endpoints can expose source code and schemas. Protect `/mcp/tools/fetch` or add authentication if you do not want raw source publicly available.
- Use a secure tunnel (paid ngrok or Cloudflare Tunnel) for production and add API auth (API key, OAuth) before exposing anything public.

## How this connects to ChatGPT and Claude

- ChatGPT
	- Use the plugin manifest URL (`/.well-known/ai-plugin.json`) so ChatGPT can install your plugin in developer mode.
	- ChatGPT will call the exposed MCP-style endpoints or the HTTP MCP tool endpoints (`/mcp/tools/search` and `/mcp/tools/fetch`) to discover tools and fetch schemas.
	- For streaming or asynchronous events, ChatGPT can open `GET /sse` to receive events from your server.

- Anthropic Claude (or other LLMs)
	- Claude can call your MCP HTTP endpoints directly (search/fetch/submit) using normal HTTP requests if you provide the URL and credentials.
	- The important part is to provide the connector the public URL and any authentication method. The MCP search/fetch shape is straightforward JSON; Claude can be instructed to call those endpoints directly.

## Next steps and recommendations

- Add API-key protection and rate limiting for `/mcp/tools/fetch`, `/sse` POST and `/mcp/submit_311_request` before public exposure.
- Implement logging and Playwright trace/screenshot collection for failed runs to speed debugging.
- Expand the mapping between `request_type` values and `chi311_automation/data` schemas to improve form filling accuracy.
- Add an integration test that runs Playwright in headed mode against a staging form and captures a screenshot.
 - Use `mcp_server_local.py` to run a local stdio-based MCP for Claude Desktop during development and testing.

## Troubleshooting

- If the SSE connection drops through ngrok, try lowering the keep-alive period or try Cloudflare Tunnel (cloudflared) — some tunnels/proxies close idle connections quickly.
- If `fastmcp` is required but not installed, you can use the included HTTP /mcp/tools endpoints as an alternative for tool discovery and fetching.

## License & contact

This project is a work-in-progress. For questions, open an issue or message the repository owner.
