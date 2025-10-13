from fastapi import APIRouter, HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import json
from typing import Dict, Any

from mcp_server import index_handlers, fetch_item

router = APIRouter()


def mcp_content_text(payload: Any) -> Dict[str, Any]:
    """Wrap payload into MCP content text item as spec requires."""
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False)
            }
        ]
    }


@router.post("/search")
async def mcp_search(body: Dict[str, Any]):
    query = body.get('query') if isinstance(body, dict) else None
    items = index_handlers()
    q = (query or '').lower()
    results = []
    for it in items:
        if not q or q in it.get('id', '').lower() or q in it.get('title', '').lower():
            results.append({"id": it['id'], "title": it['title'], "url": it['url']})

    return JSONResponse(mcp_content_text({"results": results}))


@router.post("/fetch")
async def mcp_fetch(body: Dict[str, Any]):
    item_id = body.get('id') if isinstance(body, dict) else None
    if not item_id:
        raise HTTPException(status_code=400, detail="'id' is required")

    try:
        item = fetch_item(item_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return JSONResponse(mcp_content_text(item))
