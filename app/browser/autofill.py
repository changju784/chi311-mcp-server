import os
import logging
from typing import Any, Dict

from app.schemas.request_schema import ServiceRequest

logger = logging.getLogger(__name__)


async def simulate_form_fill(request: ServiceRequest,
                             headless: bool = True,
                             dry_run: bool = True,
                             full_submit: bool = False) -> Dict[str, Any]:
    """
    Orchestrate Playwright to fill the Chicago 311 form using the
    handlers under `chi311_automation.modules`.

    This function is intentionally conservative by default (dry_run=True).
    Control behavior with the following environment variables:
      - PLAYWRIGHT_HEADLESS (true/false)
      - CHI311_DRY_RUN (true/false)
      - CHI311_FULL_SUBMIT (true/false) -- only enable if you understand risks
      - CHI311_FORM_URL (URL to the entry page for 311 form)

    Returns a dict with status and details. In dry-run mode this returns a
    simulated confirmation and some diagnostics.
    """
    # Allow environment overrides
    headless_env = os.getenv("PLAYWRIGHT_HEADLESS")
    if headless_env is not None:
        headless = headless_env.lower() not in ("0", "false", "no")

    dry_run_env = os.getenv("CHI311_DRY_RUN")
    if dry_run_env is not None:
        dry_run = dry_run_env.lower() not in ("0", "false", "no")

    full_submit_env = os.getenv("CHI311_FULL_SUBMIT")
    if full_submit_env is not None:
        full_submit = full_submit_env.lower() in ("1", "true", "yes")

    form_url = os.getenv("CHI311_FORM_URL", "https://311.chicago.gov/")

    # Lazy import Playwright so module import doesn't fail if env isn't set up
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logger.error("Playwright import failed: %s", e)
        return {
            "status": "error",
            "message": "Playwright is not installed or failed to import.",
            "details": str(e),
        }

    # Import handlers (they rely on Playwright Page)
    try:
        from chi311_automation.modules.address_handler import AddressHandler
        from chi311_automation.modules.form_handler import FormHandler
        from chi311_automation.modules.contact_handler import ContactHandler
    except Exception as e:
        logger.error("Failed to import automation handlers: %s", e)
        return {"status": "error", "message": "Automation handlers import failed", "details": str(e)}

    logger.info("Starting Playwright orchestration (headless=%s, dry_run=%s, full_submit=%s)", headless, dry_run, full_submit)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        try:
            await page.goto(form_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            # navigation failed
            await browser.close()
            logger.error("Failed to navigate to CHI311 URL: %s", e)
            return {"status": "error", "message": "Failed to navigate to CHI311 URL", "details": str(e)}

        # 1) Address entry (best-effort)
        address_handler = AddressHandler(page)
        try:
            addr_success = await address_handler.setup_with_retry(request.location, apt="")
            addr_verified = await address_handler.verify_setup() if addr_success else False
        except Exception as e:
            addr_success = False
            addr_verified = False
            logger.error("Address handler error: %s", e)

        # Prepare default results so we can reference them in any return path
        results: Dict[str, Any] = {"filled": 0, "failed": 0, "skipped": 0}

        # If we're in dry-run mode or address verification failed, stop here and return diagnostics
        if dry_run or not addr_verified:
            await browser.close()
            return {
                "status": "dry-run",
                "request_type": getattr(request, 'request_type', None),
                "location": request.location,
                "address_setup": addr_success,
                "address_verified": addr_verified,
                "confirmation_number": "SIM-311-" + request.location.replace(" ", "_"),
                "message": "Dry-run or verification failed; no submission performed.",
                "form_results": results,
            }

        # 2) Attempt to fill form fields using stored JSON schemas in chi311_automation/data
        try:
            form_handler = FormHandler(page)

            # Load form schema JSON and find the matching request_type (request.request_type)
            import json
            from pathlib import Path

            # Path resolution: go up two parents to project root
            schema_path = Path(__file__).resolve().parents[2] / 'chi311_automation' / 'data' / 'form_schemas.json'
            fields = []
            if schema_path.exists():
                try:
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema = json.load(f)
                        request_types = schema.get('request_types', [])
                        # Match by request_id or request_name fuzzy match
                        target = None
                        for rt in request_types:
                            if rt.get('request_id') == request.request_type or rt.get('request_name') == request.request_type:
                                target = rt
                                break
                        if not target:
                            # try id substring match
                            for rt in request_types:
                                if request.request_type.lower() in (rt.get('request_id', '').lower() or ''):
                                    target = rt
                                    break
                        if target:
                            fields = target.get('fields', [])
                except Exception as e:
                    logger.warning("Failed to load form_schemas.json: %s", e)

            # Prepare data mapping for FormHandler using prioritized inputs:
            # 1) explicit request.fields mapping from the request payload
            # 2) description and request_type
            data = {}
            if getattr(request, 'fields', None):
                data.update(request.fields)
            # Add description under common labels seen in schemas
            data.setdefault('Description', request.description or '')
            data.setdefault('Issue Type', getattr(request, 'request_type', None) or '')

            if fields:
                results = await form_handler.fill_form(fields, data)
            else:
                logger.info("No form schema found for request_type '%s' — skipping field fill", request.request_type)
        except Exception as e:
            logger.warning("Form handler encountered an error: %s", e)

        # 3) Contact info (best-effort) - only detect fields; don't fill unless configured
        try:
            contact_handler = ContactHandler(page)
            detected = await contact_handler.detect_fields()
        except Exception as e:
            logger.debug("Contact handler detection failed: %s", e)
            detected = {}

        # 4) Optionally proceed to submit if explicitly requested (dangerous)
        submitted = False
        confirmation = None
        if full_submit:
            try:
                # Try to find a submit/next button and click it (best-effort)
                # Use config selector if present or attempt common buttons
                try:
                    submit_button = await page.wait_for_selector('button:has-text("Submit")', timeout=2000)
                except Exception:
                    submit_button = None

                if submit_button:
                    await submit_button.click()
                    await page.wait_for_timeout(3000)
                    submitted = True
                    # Attempt to extract a confirmation number/text
                    try:
                        confirmation = await page.text_content('css=.confirmation-number')
                    except Exception:
                        confirmation = None
            except Exception as e:
                logger.error("Submission attempt failed: %s", e)

        await browser.close()

        return {
            "status": "submitted" if submitted else "completed",
            "issue_type": request.issue_type,
            "location": request.location,
            "address_setup": addr_success,
            "address_verified": addr_verified,
            "form_results": results,
            "contact_detected_fields": list(detected.keys()) if isinstance(detected, dict) else [],
            "submitted": submitted,
            "confirmation": confirmation or ("SIM-311-" + request.location.replace(" ", "_"))
        }
