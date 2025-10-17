#!/usr/bin/env python3
"""
chi311_mcp_server.py
--------------------
Local MCP server exposing Chicago 311 automation tools
to Claude Desktop (stdio-based).

Tools:
  1) list_request_types(keyword?)
  2) describe_request_type(request_name)
  3) submit_311_request(request_name, address, form_data, contact)
"""

import json
import base64
from pathlib import Path

from fastmcp import FastMCP
from PIL import Image as PILImage

from chi311_automation.automation import Chicago311Automation
from chi311_automation.catalog import RequestCatalog

from PIL import Image



# -----------------------------------------------------
# MCP Server Setup
# -----------------------------------------------------
app = FastMCP("Chicago311")

BASE_DATA_PATH = Path(__file__).parent / "chi311_automation" / "data"
catalog = RequestCatalog(BASE_DATA_PATH)


# -----------------------------------------------------
# Tool 1: List all available Chicago 311 request types
# -----------------------------------------------------
@app.tool()
def list_request_types(keyword: str = None) -> dict:
    """
    Look up Chicago 311 service request types.

    Args:
        keyword: Optional keyword to filter request types by name or description.

    Returns:
        {
          "metadata": { ... },
          "categories": [...],
          "results": [
            { "name": "...", "description": "...", "category": "..." },
            ...
          ]
        }

    Use this when the user asks things like:
      - “What can I report to Chicago 311?”
      - “Show me Public Safety issues.”
    """
    return {
        "metadata": catalog.get_metadata(),
        "categories": catalog.get_categories(),
        "results": catalog.list_simplified(keyword)
    }


# -----------------------------------------------------
# Tool 2: Describe schema for one request type
# -----------------------------------------------------
@app.tool()
def describe_request_type(request_name: str) -> dict:
    """
    Describe what information is required for a given 311 request type.

    Args:
        request_name: Exact name of the request type (e.g., "Aircraft Noise Complaint").

    Returns:
        {
          "request_name": "...",
          "category": "...",
          "total_fields": N,
          "fields": [
            {
              "label": "...",              # exact on-page label (use as JSON key)
              "field_type": "dropdown|text|textarea|date|time|multiselect|number|checkbox",
              "required": true/false,
              "options": [...],            # for dropdown/multiselect
              "example": "..." or ["..."]  # example value (format guidance)
            },
            ...
          ],
          "contact_fields": [
            {
              "name": "first_name|last_name|email|...",
              "label": "First Name",
              "type": "text|email|tel|textarea|dropdown",
              "required": true/false,
              "example": "John"
            },
            ...
          ],
          # (If enabled in your catalog) an end-to-end example payload the client can copy:
          # "example_payload": {
          #   "request_name": "...",
          #   "address": "...",
          #   "form_data": { "<exact field label>": "value", ... },
          #   "contact": { "first_name": "...", "email": "...", ... }
          # }
        }

    Tip:
      Always use the *exact* field 'label' values as keys when building form_data.
      (That is what the automation expects.)
    """
    return catalog.describe_request_type(request_name)


# -----------------------------------------------------
# Tool 3: Submit a 311 request (main automation)
# -----------------------------------------------------
@app.tool()
async def submit_311_request(
    request_name: str,
    address: str,
    form_data: dict,
    contact: dict,
    apartment: str = ""
) -> dict:
    """
    Submit a completed Chicago 311 service request via web automation.

    Args:
        request_name: The exact name of the request type
        address: Street address ONLY where the issue is located (e.g., "200 S Wacker Dr")
                 DO NOT include city, state, or zip code - just the street address.
        form_data: Dictionary of form field values (use exact field labels as keys)
        contact: Contact information dictionary for the person reporting. Supported fields:
            - first_name, last_name
            - street_address
            - city, state, postal_code, country
            - email, phone
        apartment: (OPTIONAL) Apartment/suite number for the ISSUE LOCATION (e.g., "Suite 2000", "Apt 5B")
                   This is NOT the reporter's apartment. Leave empty if issue is not at an apartment/suite.
    Returns:
        Text summary + local image file path (for Claude Desktop rendering).
    """
    automation = Chicago311Automation(BASE_DATA_PATH / "form_schemas.json")
    screenshot_path = await automation.submit_request(request_name, address, form_data, contact, apartment)

    # ✅ 작은 JPEG 미리보기 생성
    preview_path = Path(__file__).parent / "submission_preview.jpg"
    with Image.open(screenshot_path) as img:
        img.thumbnail((800, 800))
        img.convert("RGB").save(preview_path, format="JPEG", quality=80)

    # ✅ Base64 (fallback)
    with open(preview_path, "rb") as f:
        preview_b64 = base64.b64encode(f.read()).decode("utf-8")

    # ✅ 최종 응답 (파일 경로 + base64 둘 다 제공)
    return {
        "status": "success",
        "message": f"✅ Request '{request_name}' submitted successfully.",
        "preview_image": [
            {
                "type": "image",
                "path": str(preview_path.resolve()),   # <<<<<<<<<<<<<< 여기!
                "mimeType": "image/jpeg"
            },
            {
                "type": "image",
                "data": preview_b64,
                "mimeType": "image/jpeg"
            }
        ]
    }

# -----------------------------------------------------
# Entrypoint (stdio-based for Claude Desktop)
# -----------------------------------------------------
if __name__ == "__main__":
    app.run()
