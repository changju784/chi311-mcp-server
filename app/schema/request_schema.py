from pydantic import BaseModel

# TODO update fields as necessary by navigating 311 portal
class ServiceRequest(BaseModel):
    issue_type: str
    location: str
    description: str | None = None
    urgency: str | None = "medium"
