from fastapi import APIRouter
from app.schemas.request_schema import ServiceRequest
from app.browser.autofill import simulate_form_fill
import os

router = APIRouter()


@router.post("/submit_311_request")
async def submit_311_request(request: ServiceRequest):
        """Trigger Playwright automation to attempt to fill a 311 request.

        By default the orchestration is conservative (dry-run). Control behavior with env vars:
            - PLAYWRIGHT_HEADLESS (true/false)
            - CHI311_DRY_RUN (true/false)
            - CHI311_FULL_SUBMIT (true/false)
        """

        # simulate_form_fill inspects environment variables for behavior; simply await it
        result = await simulate_form_fill(request)
        return {"status": "success", "details": result}
