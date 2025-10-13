from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
from typing import Set

router = APIRouter()

# Set of asyncio.Queue objects, one per connected client
_clients: Set[asyncio.Queue] = set()


async def event_generator(queue: asyncio.Queue, request: Request):
    try:
        while True:
            # If client disconnected, stop the generator
            if await request.is_disconnected():
                break

            try:
                # wait for an event with timeout, send keep-alive if none
                data = await asyncio.wait_for(queue.get(), timeout=15.0)
                # format as SSE data frame
                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.TimeoutError:
                # keep-alive comment to prevent proxies from closing
                yield ": keep-alive\n\n"
    finally:
        # cleanup handled by caller
        return


@router.get("/sse")
async def sse_connect(request: Request):
    """Establish a Server-Sent Events connection.

    The connector (ChatGPT) should open a GET to this endpoint and keep the
    connection open. We create a per-connection asyncio.Queue that can be
    used by other endpoints (or internal code) to push events.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _clients.add(queue)

    # Ensure the queue is removed when client disconnects
    async def cleanup():
        try:
            _clients.discard(queue)
        except Exception:
            pass

    return StreamingResponse(event_generator(queue, request), media_type="text/event-stream", background=cleanup())


@router.post("/sse")
async def sse_broadcast(payload: dict):
    """Broadcast a JSON payload to all connected SSE clients.

    This allows other systems (or the ChatGPT connector) to POST messages that will
    be pushed down any active SSE connections opened via GET /sse.
    """
    if not _clients:
        # No clients connected — still return OK so caller doesn't hang
        return JSONResponse({"status": "no_clients"})

    dead = []
    for q in list(_clients):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            # unlikely with default unlimited queue, mark for removal
            dead.append(q)

    for q in dead:
        _clients.discard(q)

    return JSONResponse({"status": "broadcasted", "clients": len(_clients)})
