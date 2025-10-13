from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ContactInfo(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    anonymous: Optional[bool] = False


class ServiceRequest(BaseModel):
    """Service request payload accepted by /mcp/submit_311_request

    Fields:
      - request_type: ID from `chi311_automation/data/request_catalog.json` (e.g. "pothole_complaint")
      - location: human address string (used by AddressHandler)
      - description: free-text details to place into description fields
      - contact: optional contact information
      - fields: optional mapping of schema labels to explicit values (overrides)
    """
    request_type: str = Field(..., description="Request type id from request_catalog.json")
    location: str = Field(..., description="Human readable location/address")
    description: Optional[str] = None
    contact: Optional[ContactInfo] = None
    # Provide explicit field label -> value mapping to drive FormHandler.fill_form
    fields: Optional[Dict[str, Any]] = None
