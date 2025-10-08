# Chi311 MCP Server

**Chi311 Agent** is an AI-assisted 311 request automation system for the City of Chicago.

This repository contains the **MCP server** that allows ChatGPT to interact with your backend via structured endpoints.

---

## 🚀 Features
- FastAPI-based MCP-compatible server
- `/mcp/submit_311_request` endpoint
- Ready for browser automation (Playwright / Skyvern)
- ChatGPT plugin manifest in `.well-known/ai-plugin.json`

---

## 🏗️ Run Locally
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
