from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
from typing import Set

router = APIRouter()

# Track connected SSE clients (GET connections)
_clients: Set[asyncio.Queue] = set()


# ============================================================
# Core event stream for GET /sse (your existing real-time events)
# ============================================================
async def event_generator(queue: asyncio.Queue, request: Request):
    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                data = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _clients.discard(queue)


@router.get("/sse")
async def sse_connect(request: Request):
    """Standard GET /sse endpoint for your own system."""
    queue: asyncio.Queue = asyncio.Queue()
    _clients.add(queue)
    return StreamingResponse(event_generator(queue, request), media_type="text/event-stream")


@router.post("/sse/broadcast")
async def sse_broadcast(payload: dict):
    """Broadcast JSON payloads to all GET /sse clients."""
    if not _clients:
        return JSONResponse({"status": "no_clients"})

    for q in list(_clients):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            _clients.discard(q)

    return JSONResponse({"status": "broadcasted", "clients": len(_clients)})

@router.post("/sse")
async def mcp_sse_endpoint(request: Request):
    """
    MCP-compatible SSE endpoint for ChatGPT connectors.
    This keeps the connection open and emits periodic pings.
    """
    async def ping_stream():
        try:
            while True:
                yield "event: ping\ndata: {}\n\n"
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Connection closed by client
            return

    return StreamingResponse(ping_stream(), media_type="text/event-stream")
