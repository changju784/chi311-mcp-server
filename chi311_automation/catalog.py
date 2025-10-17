"""
catalog.py
----------
Manages both the full Chicago 311 request catalog
and detailed form schema lookups for each request type.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from chi311_automation.modules.contact_handler import ContactHandler


class RequestCatalog:
    """Unified access layer for request_catalog.json and form_schemas.json."""

    def __init__(self, base_path: Path):
        self.catalog_path = base_path / "request_catalog.json"
        self.schema_path = base_path / "form_schemas.json"

        # Load both files
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)
        with open(self.schema_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)

        root = catalog_data.get("chicago_311_request_types", {})
        self.metadata = root.get("metadata", {})
        self.requests = root.get("request_types", [])
        self.categories = root.get("categories", [])
        self.schemas = schema_data.get("request_types", [])

    # ------------------------------------------------------------------
    # Catalog-level functions
    # ------------------------------------------------------------------
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata (total count, source, etc.)."""
        return self.metadata

    def get_categories(self) -> List[str]:
        """Return high-level 311 service categories."""
        return self.categories

    def list_simplified(self, keyword: str = None) -> List[Dict[str, Any]]:
        """
        List or search all request types (name, description, category only).
        This is used when the user asks:
            "What can I report to Chicago 311?"
        """
        results = [
            {
                "name": r["name"],
                "description": r.get("description", ""),
                "category": r.get("category", "General"),
            }
            for r in self.requests
        ]
        if keyword:
            kw = keyword.lower()
            results = [r for r in results if kw in r["name"].lower() or kw in r["description"].lower()]
        return results

    # ------------------------------------------------------------------
    # Schema-level functions (per request type)
    # ------------------------------------------------------------------
    def describe_request_type(self, request_name: str) -> dict:
        """
        Return required form fields and standard contact fields
        for a given Chicago 311 request type.
        """
        with open(self.schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for req in data["request_types"]:
            if req["request_name"].lower() == request_name.lower():
                # --- Form fields from schema ---
                fields = []
                for f in req.get("fields", []):
                    fields.append({
                        "label": f["label"],
                        "field_type": f["field_type"],
                        "required": f["required"],
                        "options": f.get("options", []),
                        "example": self._example_for_type(f["field_type"], f.get("options"))
                    })

                # --- Contact fields (auto-generated from ContactHandler) ---
                contact_fields = []
                for name, config in ContactHandler.STANDARD_CONTACT_FIELDS.items():
                    example_value = self._example_for_type(config["field_types"][0])
                    contact_fields.append({
                        "name": name,
                        "label": " ".join(word.capitalize() for word in name.split("_")),
                        "type": config["field_types"][0],
                        "required": name in ["first_name", "last_name", "email"],
                        "example": example_value
                    })

                return {
                    "request_name": req["request_name"],
                    "category": req.get("category"),
                    "total_fields": len(fields),
                    "fields": fields,
                    "contact_fields": contact_fields,
                    "example_payload": {
                        "request_name": req["request_name"],
                        "address": "1234 W Division Street, Chicago, IL 60622",
                        "form_data": {f["label"]: f["example"] for f in fields},
                        "contact": {f["name"]: f["example"] for f in contact_fields}
                    }
                }

        return {"error": f"Request type '{request_name}' not found."}

    # ------------------------------------------------------------------
    # Helper: Example generator
    # ------------------------------------------------------------------
    def _example_for_type(self, field_type: str, options=None):
        """Generate example input values for different field types."""
        if field_type == "dropdown" and options:
            return options[0]
        if field_type == "multiselect" and options:
            return [options[0]]
        if field_type == "date":
            return "Dec 15, 2024"
        if field_type == "time":
            return "2:30 PM"
        if field_type == "number":
            return "123"
        if field_type == "checkbox":
            return False
        if field_type in ["email"]:
            return "john.doe@example.com"
        if field_type in ["text", "textarea"]:
            return "Sample text"
        return ""
