#!/usr/bin/env python3
"""
Complete Workflow Test for Chicago 311 Automation

This script tests the entire automation workflow from address setup to form submission.
It covers all major functionality: AddressHandler, FormHandler, and ContactHandler.
This is the primary integration test for the Chicago 311 automation system.
"""

import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules import AddressHandler, FormHandler, ContactHandler

# Test configuration constants
TEST_REQUEST_NAME = "Consumer Fraud Complaint"
TEST_ADDRESS = "123 Main St, Chicago, IL"
TEST_APT_SUITE = "Apt 1B"
BROWSER_VIEWPORT = {'width': 1280, 'height': 720}
BROWSER_SLOW_MO = 1000  # milliseconds


def load_test_request() -> Optional[Dict[str, Any]]:
    """
    Load the test request from form schemas.
    
    Returns:
        Dictionary containing request data or None if not found
    """
    data_path = Path(__file__).parent.parent / 'data' / 'form_schemas.json'
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find the test request (has dropdown, multiselect, date, time, textarea, and anonymous button)
        for request in data['request_types']:
            if (request.get('analysis_success', False) and 
                request['request_name'] == TEST_REQUEST_NAME):
                return request
        
        return None
    except Exception as e:
        print(f"❌ Error loading form schemas: {e}")
        return None


def generate_test_contact_data() -> Dict[str, Any]:
    """
    Generate test contact data for form filling.
    
    Returns:
        Dictionary containing sample contact information
    """
    return {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john.doe@example.com',
        'phone': '312-555-0123',
        'street_address': '123 Main Street, Apt 4B',
        'city': 'Chicago',
        'state': 'IL',
        'postal_code': '60601',
        'country': 'United States',
        'anonymous': False
    }


def generate_test_form_data(fields: list) -> Dict[str, Any]:
    """
    Generate test form data based on field requirements.
    
    Args:
        fields: List of form field definitions
        
    Returns:
        Dictionary containing sample form data
    """
    form_data = {}
    
    for field in fields:
        if field.get('required', False):
            label = field.get('label', '')
            field_type = field.get('field_type', '')
            
            if field_type == 'dropdown' and field.get('options'):
                form_data[label] = field['options'][0]
            elif field_type == 'multiselect' and field.get('options'):
                # Select first and third options (if available)
                options = field['options']
                if len(options) >= 3:
                    form_data[label] = [options[0], options[2]]  # First and third
                elif len(options) >= 2:
                    form_data[label] = [options[0], options[1]]  # First and second
                else:
                    form_data[label] = [options[0]]  # Only first
            elif field_type == 'date':
                form_data[label] = "Dec 15, 2024"
            elif field_type == 'time':
                form_data[label] = "2:30 PM"
            elif field_type == 'number':
                form_data[label] = "123"
            elif field_type in ['text', 'textarea']:
                form_data[label] = "Sample text"
    
    return form_data


async def test_complete_workflow():
    """
    Test the complete Chicago 311 automation workflow with a sample request.
    
    This function tests the entire automation pipeline:
    1. Address setup (if required)
    2. Form field filling
    3. Navigation to contact page
    4. Contact information filling
    5. Final submission
    """
    # Load test request data
    test_request = load_test_request()
    if not test_request:
        print("❌ No successful form analysis found for test request")
        return
    
    print("Testing Complete Chicago 311 Automation Workflow")
    print("=" * 70)
    print(f"Request: {test_request['request_name']}")
    print(f"URL: {test_request['url']}")
    print("Testing: AddressHandler → FormHandler → ContactHandler")
    print("=" * 70)
    
    # Generate test data
    contact_data = generate_test_contact_data()
    form_data = generate_test_form_data(test_request.get('fields', []))
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=BROWSER_SLOW_MO)
        context = await browser.new_context(viewport=BROWSER_VIEWPORT)
        page = await context.new_page()
        
        try:
            # Step 1: Navigate to the form
            print("1. Navigating to form...")
            await page.goto(test_request['url'], wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # Step 2: Check if address setup is needed
            print("2. Checking if address setup is needed...")
            address_input = await page.query_selector('input.slds-input[placeholder*="address" i]')
            if address_input:
                print("   📍 Address field found, setting up address...")
                address_handler = AddressHandler(page)
                await address_handler.setup()
            else:
                print("   ✅ No address field found, proceeding directly to form...")
            
            # Step 3: Fill the form to get to contact info page
            print("3. Filling form to reach contact info page...")
            fields = test_request.get('fields', [])
            
            # Fill form using generated test data
            form_handler = FormHandler(page)
            fill_results = await form_handler.fill_form(fields, form_data)
            print(f"   📊 Form fill results: {fill_results['filled']} filled, {fill_results['failed']} failed")
            
            # Step 4: Click Next to get to contact page
            print("4. Clicking Next to reach contact page...")
            next_clicked = await form_handler.click_next()
            if not next_clicked:
                print("   ❌ Failed to click Next button")
                return
            
            # Wait for contact page to load
            await page.wait_for_timeout(3000)
            
            # Step 5: Test ContactHandler (Final Step)
            print("5. Testing ContactHandler (Final Step)...")
            contact_handler = ContactHandler(page)
            
            # Detect contact fields
            detected_fields = await contact_handler.detect_fields()
            print(f"   📋 Detected {len(detected_fields)} standard contact field types")
            for field_type, field in detected_fields.items():
                print(f"     • {field_type}: {field.label}")
            
            # Fill contact info
            contact_results = await contact_handler.fill_contact_info(contact_data)
            print(f"   📊 Contact fill results: {contact_results['filled_count']} filled, {contact_results['failed_count']} failed, {contact_results['skipped_count']} skipped")
            
            # Verify all fields were filled by checking page content
            print("\n6. Verifying filled fields...")
            for field_type, value in contact_data.items():
                if field_type == 'anonymous':
                    continue  # Skip anonymous checkbox verification
                
                # Try to find the field and check if it has the expected value
                field_selectors = [
                    f'input[name="{field_type}"]',
                    f'textarea[name="{field_type}"]',
                    f'input[name="{field_type.replace("_", "")}"]',
                    f'textarea[name="{field_type.replace("_", "")}"]'
                ]
                
                field_found = False
                for selector in field_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            actual_value = await element.input_value()
                            if actual_value == str(value):
                                print(f"   ✅ {field_type}: '{value}' ✓")
                            else:
                                print(f"   ❌ {field_type}: Expected '{value}', got '{actual_value}'")
                            field_found = True
                            break
                    except:
                        continue
                
                if not field_found:
                    print(f"   ⚠️  {field_type}: Field not found for verification")
            
            # Step 7: Click submit button (Final Action)
            print("\n7. Clicking submit button (Final Action)...")
            submit_clicked = await contact_handler.click_submit()
            if submit_clicked:
                print("   ✅ Contact info form submitted successfully")
                # Wait to see the result
                await page.wait_for_timeout(5000)
            else:
                print("   ❌ Failed to click submit button")
                await page.wait_for_timeout(3000)
                
        except Exception as e:
            print(f"❌ Error during test: {e}")
            
        finally:
            await browser.close()


def print_section_header(title: str, width: int = 80) -> None:
    """Print formatted section header."""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


async def main():
    """
    Main function to run the complete workflow test.
    
    This function sets up the test environment and runs the complete
    automation workflow test with proper error handling and reporting.
    """
    print_section_header("Chicago 311 Complete Workflow Test")
    
    try:
        await test_complete_workflow()
        print("\n✅ Complete workflow test finished successfully!")
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
