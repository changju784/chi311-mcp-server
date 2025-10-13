from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
from typing import Set, Dict
import logging

router = APIRouter()
logger = logging.getLogger("chi311.mcp")

# Track connected SSE clients (GET connections)
_clients: Set[asyncio.Queue] = set()

# Track MCP sessions
_mcp_sessions: Dict[str, dict] = {}


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
    Implements the MCP SSE transport protocol:
    1. Sends 'endpoint' event with messages URL
    2. Sends periodic keep-alive pings
    """
    import uuid
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    async def mcp_stream():
        try:
            # Step 1: Send endpoint event with session-specific messages URL
            base_url = str(request.base_url).rstrip("/")
            endpoint_url = f"{base_url}/messages?session_id={session_id}"
            yield f"event: endpoint\n"
            yield f"data: {endpoint_url}\n\n"
            
            # Step 2: Send periodic keep-alive pings
            while True:
                await asyncio.sleep(15)
                yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            return

    # Store session for /messages endpoint
    _mcp_sessions[session_id] = {"created_at": asyncio.get_event_loop().time()}
    
    return StreamingResponse(
        mcp_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/messages")
async def mcp_messages_endpoint(request: Request):
    """
    MCP messages endpoint - handles JSON-RPC requests from ChatGPT.
    """
    session_id = request.query_params.get("session_id")
    
    if not session_id or session_id not in _mcp_sessions:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Invalid session"}, "id": None},
            status_code=400
        )
    
    try:
        body = await request.json()
        logger.info(f"MCP message received (session {session_id}): {body}")
        
        # Handle initialize request
        if body.get("method") == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Chi311 MCP Server",
                        "version": "0.1.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            })
        
        # Handle tools/list request
        elif body.get("method") == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search Chi311 automation handlers and form schemas",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"}
                                }
                            }
                        },
                        {
                            "name": "fetch",
                            "description": "Fetch module or form schema by ID",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "description": "Item ID to fetch"}
                                },
                                "required": ["id"]
                            }
                        }
                    ]
                }
            })
        
        # Handle tools/call request (invoke search or fetch)
        elif body.get("method") == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name == "search":
                # Import and call search function from mcp_server.py
                from mcp_server import index_handlers
                results = index_handlers()
                query = tool_args.get("query", "").lower()
                filtered = [r for r in results if not query or query in r.get("id", "").lower() or query in r.get("title", "").lower()]
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({"results": filtered}, indent=2)
                            }
                        ]
                    }
                })
            
            elif tool_name == "fetch":
                # Import and call fetch function from mcp_server.py
                from mcp_server import fetch_item
                item_id = tool_args.get("id")
                try:
                    result = fetch_item(item_id)
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2)
                                }
                            ]
                        }
                    })
                except ValueError as e:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "error": {
                            "code": -32602,
                            "message": str(e)
                        }
                    })
            
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                })
        
        # Unknown method
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {body.get('method')}"
                }
            })
    
    except Exception as e:
        logger.error(f"Error handling MCP message: {e}", exc_info=True)
        try:
            msg_id = body.get("id") if 'body' in locals() and body else None
        except:
            msg_id = None
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            },
            "id": msg_id
        }, status_code=500)
