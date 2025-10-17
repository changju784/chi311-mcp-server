"""
automation.py
-------------
High-level wrapper that coordinates AddressHandler, FormHandler,
and ContactHandler to complete a Chicago 311 submission via Playwright.

This version mirrors the proven working flow from the integration test:
1) navigate -> 2) optional address setup -> 3) form fill -> 4) next ->
5) contact detect/fill -> 6) submit -> 7) screenshot
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from playwright.async_api import async_playwright, Page
from .modules import AddressHandler, FormHandler, ContactHandler


class Chicago311Automation:
    """
    Thin orchestration layer that reuses the exact, working logic pattern
    from the integration test. It does not invent new fill logic; it
    simply wires AddressHandler / FormHandler / ContactHandler together.
    """

    def __init__(
        self,
        schema_path: Path,
        *,
        viewport: Dict[str, int] = None,
        headless: bool = False,
        slow_mo_ms: int = 1000,  # keep slow for debug parity with test
        extra_wait_ms: int = 3000
    ):
        """
        Args:
            schema_path: path to data/form_schemas.json
            viewport: playwright viewport (width/height). default 1280x720
            headless: launch headless browser (default False for debugging)
            slow_mo_ms: playwright slow_mo milliseconds (default 1000 to match test)
            extra_wait_ms: small waits after navigation and transitions
        """
        self.schema_path = Path(schema_path)
        with open(self.schema_path, "r", encoding="utf-8") as f:
            self.schemas = json.load(f)

        self.viewport = viewport or {"width": 1280, "height": 720}
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
        self.extra_wait_ms = extra_wait_ms

        # default output locations
        root = Path(__file__).parent.parent
        self.screenshot_ok = root / "submission_result.png"
        self.screenshot_err = root / "submission_error.png"

    # --------------------------
    # Public API
    # --------------------------
    def get_request_schema(self, request_name: str) -> dict:
        for r in self.schemas["request_types"]:
            if r["request_name"].lower() == request_name.lower():
                return r
        raise ValueError(f"Request type '{request_name}' not found")

    async def submit_request(
        self,
        request_name: str,
        address: str,
        form_data: Dict[str, Any],
        contact: Dict[str, Any],
        apartment: str = "",
    ) -> Path:
        """
        Run the full automation using the same sequence as the working test.

        IMPORTANT:
        - form_data keys must match the field labels from form_schemas.json
          (e.g., '*1. Which airport...').
        - contact keys should match ContactHandler expected keys
          (e.g., first_name, last_name, email, phone, ...).

        Returns:
            Path to a final screenshot (PNG). On failure, returns an error screenshot.
        """
        req = self.get_request_schema(request_name)
        url = req["url"]
        fields = req.get("fields", [])

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo_ms)
            context = await browser.new_context(viewport=self.viewport)
            page = await context.new_page()

            try:
                # 1) Navigate
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(self.extra_wait_ms)

                # 2) Optional address step (mirror test logic)
                address_input = await page.query_selector('input.slds-input[placeholder*="address" i]')
                if address_input:
                    addr_handler = AddressHandler(page)
                    # Use the handler's own internal flow; it knows how to set up the address UI
                    await addr_handler.setup(address=address, apt=apartment)

                # 3) Form step — use existing FormHandler logic
                form_handler = FormHandler(page)
                fill_results = await form_handler.fill_form(fields, form_data)
                # (Optional) sanity check: if many failed, you may decide to raise
                # but we keep parity with test and just proceed to Next.
                # print(f"[automation] form fill -> filled={fill_results['filled']} failed={fill_results['failed']}")

                # 4) Next to contact page
                next_clicked = await form_handler.click_next()
                if not next_clicked:
                    # Take a screenshot and raise to bubble up error
                    await page.screenshot(path=str(self.screenshot_err))
                    raise RuntimeError("Failed to click Next to reach contact page")
                await page.wait_for_timeout(self.extra_wait_ms)

                # 5) Contact step — detect first, then fill (same as test)
                contact_handler = ContactHandler(page)
                await contact_handler.detect_fields()
                contact_results = await contact_handler.fill_contact_info(contact)
                # print(f"[automation] contact fill -> {contact_results}")

                # 6) Submit
                submitted = await contact_handler.click_submit()
                if not submitted:
                    await page.screenshot(path=str(self.screenshot_err))
                    raise RuntimeError("Failed to click Submit on contact page")

                # small wait to allow any confirmation transition
                await page.wait_for_timeout(self.extra_wait_ms)

                # 7) Screenshot success
                await page.screenshot(path=str(self.screenshot_ok))
                return self.screenshot_ok

            except Exception as e:
                # Capture failure state to help debugging
                try:
                    await page.screenshot(path=str(self.screenshot_err))
                except Exception:
                    pass
                # Bubble the error up; your MCP layer can catch and format the message
                raise RuntimeError(f"Automation failed: {e}") from e

            finally:
                await browser.close()
