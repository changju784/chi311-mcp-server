from fastapi import APIRouter
from app.schemas.request_schema import ServiceRequest
from app.browser.autofill import simulate_form_fill

router = APIRouter()

@router.post("/submit_311_request")
def submit_311_request(request: ServiceRequest):
    """Simulates filling out a 311 request form via browser automation."""
    result = simulate_form_fill(request)
    return {"status": "success", "details": result}
