#!/usr/bin/env python3
"""
Contact Schema Analyzer for Chicago 311 Request Types

Analyzes contact information page schemas for all Chicago 311 request types using parallel processing.
This script extends the form detection to also analyze the contact info page, extracting information
about contact fields, their types, validation requirements, and the anonymous option.
"""

import asyncio
import json
import sys
import fcntl
import os
import signal
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules import AddressHandler, FormHandler


class FileLocker:
    """
    Thread-safe file operations for parallel processing.
    
    Provides atomic read/write operations with file locking to prevent
    race conditions when multiple workers are writing to the same file.
    """
    
    def __init__(self, file_path: Path):
        """
        Initialize file locker.
        
        Args:
            file_path: Path to the file to manage
        """
        self.file_path = file_path
        self.lock_file = file_path.with_suffix('.lock')
    
    def read_json(self) -> Dict[str, Any]:
        """
        Read JSON file with file locking.
        
        Returns:
            Dictionary containing the JSON data
        """
        if not self.file_path.exists():
            return {"request_types": []}
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            with fcntl.flock(f.fileno(), fcntl.LOCK_SH):  # Shared lock for reading
                return json.load(f)
    
    def write_json(self, data: Dict[str, Any]) -> None:
        """
        Write JSON file with file locking.
        
        Args:
            data: Dictionary to write as JSON
        """
        temp_file = self.file_path.with_suffix('.tmp')
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                with fcntl.flock(f.fileno(), fcntl.LOCK_EX):  # Exclusive lock for writing
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.rename(temp_file, self.file_path)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e


@dataclass
class ContactField:
    """
    Represents a contact information field.
    
    Contains all relevant information about a contact field including
    its type, label, validation requirements, and interaction methods.
    """
    field_type: str  # 'text', 'email', 'phone', 'dropdown', 'checkbox', 'unknown'
    label: str
    name: str
    id: str
    required: bool
    placeholder: str = None
    maxlength: int = None
    pattern: str = None  # HTML pattern attribute
    input_type: str = None  # HTML input type
    options: List[str] = None  # For dropdowns
    css_selector: str = None
    xpath: str = None
    component_type: str = None
    special_notes: str = None
    validation_rules: str = None  # Any validation requirements


@dataclass
class ContactInfoAnalysis:
    """
    Analysis results for a single request type's contact info page.
    
    Contains comprehensive information about the contact page structure,
    field types, validation requirements, and any issues found.
    """
    request_id: str
    request_name: str
    category: str
    url: str
    analysis_success: bool
    error_message: str = None
    processing_time_seconds: float = None
    fields: List[ContactField] = None
    anonymous_option_available: bool = False
    anonymous_option_text: str = None
    total_fields: int = 0
    required_fields: int = 0
    optional_fields: int = 0
    field_types_found: List[str] = None
    unique_fields: List[str] = None  # Fields not in standard set


class ContactSchemaAnalyzer:
    """
    Analyzes contact information page schemas for all Chicago 311 request types.
    
    This class handles parallel processing of request types to analyze their
    contact information pages, extract field information, and identify patterns.
    """
    
    def __init__(self, output_file: Path, max_concurrent: int = 3, 
                 headless: bool = False, slow_mo: int = 500):
        """
        Initialize the contact schema analyzer.
        
        Args:
            output_file: Path to the output JSON file
            max_concurrent: Maximum number of concurrent browser instances
            headless: Whether to run browsers in headless mode
            slow_mo: Delay between actions in milliseconds
        """
        self.output_file = output_file
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.slow_mo = slow_mo
        self.file_locker = FileLocker(output_file)
        self.active_browsers = []
        self.setup_signal_handler()
    
    def setup_signal_handler(self) -> None:
        """Setup Ctrl+C handler for graceful shutdown."""
        def signal_handler(signum, frame):
            print(f"\n🛑 Ctrl+C detected! Closing all browsers...")
            
            # Kill all chromium processes
            try:
                import subprocess
                subprocess.run(['pkill', '-f', 'chromium'], capture_output=True)
            except:
                pass
            
            print(f"✅ All browsers closed.")
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
    
    async def analyze_contact_page(self, request: Dict[str, Any], worker_id: int) -> Dict[str, Any]:
        """
        Analyze contact information page for a single request type.
        
        Args:
            request: Dictionary containing request type information
            worker_id: ID of the worker for logging
            
        Returns:
            Dictionary with analysis results
        """
        request_name = request.get('name', 'Unknown')
        request_url = request.get('url', '')
        
        print(f"🎯 [Worker {worker_id}] Starting: {request_name}")
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    slow_mo=self.slow_mo
                )
                self.active_browsers.append(browser)
                
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                try:
                    # Navigate to the request form
                    await page.goto(request_url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(3000)
                    
                    # Check if address setup is needed
                    address_input = await page.query_selector('input.slds-input[placeholder*="address" i]')
                    if address_input:
                        print(f"📍 [Worker {worker_id}] Address field found, setting up address...")
                        address_handler = AddressHandler(page)
                        await address_handler.setup()
                        await page.wait_for_timeout(3000)
                    else:
                        print(f"✅ [Worker {worker_id}] No address field found, proceeding directly...")
                    
                    # Fill form to get to contact page
                    print(f"📝 [Worker {worker_id}] Filling form to reach contact page...")
                    form_handler = FormHandler(page)
                    
                    # Generate sample form data
                    form_data = self.generate_sample_form_data(request.get('fields', []))
                    fill_results = await form_handler.fill_form(request.get('fields', []), form_data)
                    print(f"📊 [Worker {worker_id}] Form fill results: {fill_results['filled']} filled, {fill_results['failed']} failed")
                    
                    # Click Next to get to contact page
                    next_clicked = await form_handler.click_next()
                    if not next_clicked:
                        print(f"❌ [Worker {worker_id}] Failed to click Next button")
                        return self.create_failed_analysis(request, "Failed to navigate to contact page", start_time)
                    
                    # Wait for contact page to load
                    await page.wait_for_timeout(3000)
                    
                    # Extract contact fields
                    contact_fields = await self.extract_contact_fields(page, worker_id)
                    
                    # Analyze the extracted fields
                    analysis = self.analyze_contact_fields(contact_fields, request, worker_id)
                    
                    processing_time = asyncio.get_event_loop().time() - start_time
                    analysis.processing_time_seconds = processing_time
                    
                    print(f"✅ [Worker {worker_id}] Completed: {request_name} ({processing_time:.1f}s)")
                    return asdict(analysis)
                    
                except Exception as e:
                    processing_time = asyncio.get_event_loop().time() - start_time
                    print(f"❌ [Worker {worker_id}] Failed: {request_name} - {str(e)}")
                    return self.create_failed_analysis(request, str(e), start_time)
                
                finally:
                    await browser.close()
                    if browser in self.active_browsers:
                        self.active_browsers.remove(browser)
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            print(f"❌ [Worker {worker_id}] Critical error: {request_name} - {str(e)}")
            return self.create_failed_analysis(request, f"Critical error: {str(e)}", start_time)
    
    def generate_sample_form_data(self, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate sample form data for filling forms.
        
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
                    options = field['options']
                    if len(options) >= 2:
                        form_data[label] = [options[0], options[1]]
                    else:
                        form_data[label] = [options[0]]
                elif field_type == 'date':
                    form_data[label] = "Dec 15, 2024"
                elif field_type == 'time':
                    form_data[label] = "2:30 PM"
                elif field_type == 'number':
                    form_data[label] = "123"
                elif field_type in ['text', 'textarea']:
                    form_data[label] = "Sample text"
        
        return form_data
    
    def create_failed_analysis(self, request: Dict[str, Any], error_message: str, start_time: float) -> Dict[str, Any]:
        """
        Create a failed analysis result.
        
        Args:
            request: Original request information
            error_message: Error message describing the failure
            start_time: Start time of the analysis
            
        Returns:
            Dictionary with failed analysis results
        """
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return {
            'request_id': request.get('id', ''),
            'request_name': request.get('name', ''),
            'category': request.get('category', ''),
            'url': request.get('url', ''),
            'analysis_success': False,
            'error_message': error_message,
            'processing_time_seconds': processing_time,
            'fields': [],
            'anonymous_option_available': False,
            'anonymous_option_text': None,
            'total_fields': 0,
            'required_fields': 0,
            'optional_fields': 0,
            'field_types_found': [],
            'unique_fields': []
        }
    
    async def extract_contact_fields(self, page: Page, worker_id: int) -> List[ContactField]:
        """
        Extract all contact fields from the current page.
        
        Args:
            page: Playwright page object
            worker_id: ID of the worker for logging
            
        Returns:
            List of ContactField objects
        """
        fields = []
        
        print(f"🔍 [Worker {worker_id}] Extracting contact fields...")
        
        # Extract standard HTML fields
        standard_fields = await self.extract_standard_fields(page, worker_id)
        fields.extend(standard_fields)
        
        # Extract Lightning components
        lightning_fields = await self.extract_lightning_fields(page, worker_id)
        fields.extend(lightning_fields)
        
        # Remove duplicates
        seen_fields = set()
        unique_fields = []
        for field in fields:
            field_key = (field.name, field.id, field.label)
            if field_key not in seen_fields:
                seen_fields.add(field_key)
                unique_fields.append(field)
        
        print(f"📋 [Worker {worker_id}] Extracted {len(unique_fields)} unique contact fields")
        return unique_fields
    
    async def extract_standard_fields(self, page: Page, worker_id: int) -> List[ContactField]:
        """
        Extract standard HTML contact fields.
        
        Args:
            page: Playwright page object
            worker_id: ID of the worker for logging
            
        Returns:
            List of ContactField objects
        """
        fields = []
        
        # Standard contact field selectors
        contact_selectors = [
            'input[name="firstname"]',
            'input[name="lastname"]', 
            'textarea[name="address"]',
            'input[name="city"]',
            'input[name="state"]',
            'input[name="postalcode"]',
            'input[name="country"]',
            'input[name="email"]',
            'input[name="phone"]',
            'input[type="checkbox"][name="submitAnonymously"]'
        ]
        
        for selector in contact_selectors:
            elements = await page.query_selector_all(selector)
            for element in elements:
                field = await self.analyze_contact_field(element, page)
                if field and field.label.strip():
                    fields.append(field)
        
        return fields
    
    async def extract_lightning_fields(self, page: Page, worker_id: int) -> List[ContactField]:
        """
        Extract Lightning component contact fields.
        
        Args:
            page: Playwright page object
            worker_id: ID of the worker for logging
            
        Returns:
            List of ContactField objects
        """
        fields = []
        
        # Look for Lightning input components
        lightning_inputs = await page.query_selector_all('lightning-input')
        for input_elem in lightning_inputs:
            field = await self.analyze_lightning_input(input_elem, page)
            if field:
                fields.append(field)
        
        # Look for Lightning textarea components
        lightning_textareas = await page.query_selector_all('lightning-textarea')
        for textarea_elem in lightning_textareas:
            field = await self.analyze_lightning_textarea(textarea_elem, page)
            if field:
                fields.append(field)
        
        # Look for anonymous checkbox
        anonymous_checkbox = await page.query_selector('lightning-primitive-input-toggle')
        if anonymous_checkbox:
            field = await self.analyze_anonymous_checkbox(anonymous_checkbox, page)
            if field:
                fields.append(field)
        
        return fields
    
    async def analyze_contact_field(self, element, page: Page) -> Optional[ContactField]:
        """
        Analyze a single contact field element.
        
        Args:
            element: Playwright element handle
            page: Playwright page object
            
        Returns:
            ContactField object or None if analysis fails
        """
        try:
            # Get basic attributes
            name = await element.get_attribute('name') or ''
            field_id = await element.get_attribute('id') or ''
            required = await element.get_attribute('required') is not None
            placeholder = await element.get_attribute('placeholder') or ''
            maxlength = await element.get_attribute('maxlength')
            pattern = await element.get_attribute('pattern') or ''
            input_type = await element.get_attribute('type') or 'text'
            
            # Get label
            label = await self.get_field_label(element, field_id, name, page)
            
            # Determine field type
            field_type = self.determine_field_type(name, input_type, label)
            
            # Get CSS selector
            css_selector = f'input[name="{name}"]' if name else f'input[id="{field_id}"]'
            
            return ContactField(
                field_type=field_type,
                label=label,
                name=name,
                id=field_id,
                required=required,
                placeholder=placeholder,
                maxlength=int(maxlength) if maxlength else None,
                pattern=pattern if pattern else None,
                input_type=input_type,
                options=None,
                css_selector=css_selector,
                xpath=None,
                component_type='standard',
                special_notes=None,
                validation_rules=None
            )
            
        except Exception as e:
            print(f"⚠️ Error analyzing contact field: {e}")
            return None
    
    async def analyze_lightning_input(self, element, page: Page) -> Optional[ContactField]:
        """
        Analyze a Lightning input component.
        
        Args:
            element: Playwright element handle
            page: Playwright page object
            
        Returns:
            ContactField object or None if analysis fails
        """
        try:
            # Get input element within Lightning component
            input_elem = await element.query_selector('input')
            if not input_elem:
                return None
            
            # Get attributes
            name = await input_elem.get_attribute('name') or ''
            field_id = await input_elem.get_attribute('id') or ''
            required = await input_elem.get_attribute('required') is not None
            placeholder = await input_elem.get_attribute('placeholder') or ''
            maxlength = await input_elem.get_attribute('maxlength')
            pattern = await input_elem.get_attribute('pattern') or ''
            input_type = await input_elem.get_attribute('type') or 'text'
            
            # Get label
            label = await self.get_field_label(element, field_id, name, page)
            
            # Determine field type
            field_type = self.determine_field_type(name, input_type, label)
            
            # Get CSS selector
            css_selector = f'lightning-input[name="{name}"]' if name else f'lightning-input[data-field-id="{field_id}"]'
            
            return ContactField(
                field_type=field_type,
                label=label,
                name=name,
                id=field_id,
                required=required,
                placeholder=placeholder,
                maxlength=int(maxlength) if maxlength else None,
                pattern=pattern if pattern else None,
                input_type=input_type,
                options=None,
                css_selector=css_selector,
                xpath=None,
                component_type='lightning-input',
                special_notes=None,
                validation_rules=None
            )
            
        except Exception as e:
            print(f"⚠️ Error analyzing Lightning input: {e}")
            return None
    
    async def analyze_lightning_textarea(self, element, page: Page) -> Optional[ContactField]:
        """
        Analyze a Lightning textarea component.
        
        Args:
            element: Playwright element handle
            page: Playwright page object
            
        Returns:
            ContactField object or None if analysis fails
        """
        try:
            # Get textarea element within Lightning component
            textarea_elem = await element.query_selector('textarea')
            if not textarea_elem:
                return None
            
            # Get attributes
            name = await textarea_elem.get_attribute('name') or ''
            field_id = await textarea_elem.get_attribute('id') or ''
            maxlength = await textarea_elem.get_attribute('maxlength')
            
            # Get label
            label = await self.get_field_label(element, field_id, name, page)
            
            # Get CSS selector
            css_selector = f'lightning-textarea[name="{name}"]' if name else f'lightning-textarea[data-field-id="{field_id}"]'
            
            return ContactField(
                field_type='textarea',
                label=label,
                name=name,
                id=field_id,
                required=False,  # Lightning textareas usually don't have required attribute
                placeholder=None,
                maxlength=int(maxlength) if maxlength else None,
                pattern=None,
                input_type='textarea',
                options=None,
                css_selector=css_selector,
                xpath=None,
                component_type='lightning-textarea',
                special_notes=None,
                validation_rules=None
            )
            
        except Exception as e:
            print(f"⚠️ Error analyzing Lightning textarea: {e}")
            return None
    
    async def analyze_anonymous_checkbox(self, element, page: Page) -> Optional[ContactField]:
        """
        Analyze the anonymous checkbox component.
        
        Args:
            element: Playwright element handle
            page: Playwright page object
            
        Returns:
            ContactField object or None if analysis fails
        """
        try:
            # Get label
            label_elem = await element.query_selector('label')
            label = await label_elem.inner_text() if label_elem else 'Anonymous'
            
            return ContactField(
                field_type='checkbox',
                label=label,
                name='anonymous',
                id='anonymous',
                required=False,
                placeholder=None,
                maxlength=None,
                pattern=None,
                input_type='checkbox',
                options=None,
                css_selector='lightning-primitive-input-toggle',
                xpath=None,
                component_type='lightning-primitive-input-toggle',
                special_notes='Anonymous option checkbox',
                validation_rules=None
            )
            
        except Exception as e:
            print(f"⚠️ Error analyzing anonymous checkbox: {e}")
            return None
    
    def determine_field_type(self, name: str, input_type: str, label: str) -> str:
        """
        Determine the field type based on name, input type, and label.
        
        Args:
            name: Field name attribute
            input_type: HTML input type
            label: Field label text
            
        Returns:
            String representing the field type
        """
        name_lower = name.lower()
        label_lower = label.lower()
        
        if 'email' in name_lower or 'email' in label_lower:
            return 'email'
        elif 'phone' in name_lower or 'phone' in label_lower:
            return 'phone'
        elif input_type == 'checkbox':
            return 'checkbox'
        elif input_type == 'textarea':
            return 'textarea'
        else:
            return 'text'
    
    async def get_field_label(self, element, field_id: str, field_name: str, page: Page) -> str:
        """
        Get field label using multiple strategies.
        
        Args:
            element: Playwright element handle
            field_id: Field ID attribute
            field_name: Field name attribute
            page: Playwright page object
            
        Returns:
            String containing the field label
        """
        try:
            # Strategy 1: Look for label with for attribute
            if field_id:
                label_elem = await page.query_selector(f'label[for="{field_id}"]')
                if label_elem:
                    return await label_elem.inner_text()
            
            # Strategy 2: Look for parent label
            parent = await element.query_selector('xpath=..')
            if parent:
                parent_label = await parent.query_selector('label')
                if parent_label:
                    return await parent_label.inner_text()
            
            # Strategy 3: Look for aria-labelledby
            labelledby = await element.get_attribute('aria-labelledby')
            if labelledby:
                label_elem = await page.query_selector(f'#{labelledby}')
                if label_elem:
                    return await label_elem.inner_text()
            
            # Strategy 4: Look for nearby text
            nearby_text = await element.evaluate('''
                (element) => {
                    const parent = element.closest('.slds-form-element');
                    if (parent) {
                        const label = parent.querySelector('.slds-form-element__label');
                        if (label) return label.textContent.trim();
                    }
                    return '';
                }
            ''')
            
            if nearby_text:
                return nearby_text
            
            return ''
            
        except Exception as e:
            print(f"⚠️ Error getting field label: {e}")
            return ''
    
    def analyze_contact_fields(self, fields: List[ContactField], request: Dict[str, Any], worker_id: int) -> ContactInfoAnalysis:
        """
        Analyze the extracted contact fields and create analysis results.
        
        Args:
            fields: List of extracted ContactField objects
            request: Original request information
            worker_id: ID of the worker for logging
            
        Returns:
            ContactInfoAnalysis object with analysis results
        """
        # Count field types
        field_types = {}
        required_count = 0
        optional_count = 0
        anonymous_available = False
        anonymous_text = None
        
        for field in fields:
            field_type = field.field_type
            if field_type not in field_types:
                field_types[field_type] = 0
            field_types[field_type] += 1
            
            if field.required:
                required_count += 1
            else:
                optional_count += 1
            
            if field.name == 'anonymous' or 'anonymous' in field.label.lower():
                anonymous_available = True
                anonymous_text = field.label
        
        # Identify unique fields (not in standard set)
        standard_fields = {'firstname', 'lastname', 'address', 'city', 'state', 'postalcode', 'country', 'email', 'phone', 'anonymous'}
        unique_fields = []
        for field in fields:
            if field.name not in standard_fields and field.name:
                unique_fields.append(field.name)
        
        return ContactInfoAnalysis(
            request_id=request.get('id', ''),
            request_name=request.get('name', ''),
            category=request.get('category', ''),
            url=request.get('url', ''),
            analysis_success=True,
            fields=fields,
            anonymous_option_available=anonymous_available,
            anonymous_option_text=anonymous_text,
            total_fields=len(fields),
            required_fields=required_count,
            optional_fields=optional_count,
            field_types_found=list(field_types.keys()),
            unique_fields=unique_fields
        )
    
    async def process_all_requests(self) -> None:
        """
        Process all request types in parallel with workers.
        
        Loads request types from the form analysis results and processes them
        using the specified number of concurrent browser instances.
        """
        print("🚀 Starting Chicago 311 contact schema analysis...")
        
        # Load form analysis results
        form_analysis_file = Path(__file__).parent.parent / 'data' / 'form_schemas.json'
        try:
            with open(form_analysis_file, 'r', encoding='utf-8') as f:
                form_data = json.load(f)
                successful_requests = [req for req in form_data['request_types'] if req.get('analysis_success', False)]
        except Exception as e:
            print(f"❌ Error loading form analysis data: {e}")
            return
        
        print(f"📋 Found {len(successful_requests)} successful form analyses to process")
        
        # Load existing results
        existing_data = self.file_locker.read_json()
        existing_requests = {req['request_id']: req for req in existing_data.get('request_types', [])}
        
        # Filter out already processed requests
        pending_requests = []
        for request in successful_requests:
            if request.get('request_id', '') not in existing_requests:
                pending_requests.append(request)
        
        print(f"📝 {len(pending_requests)} requests pending contact analysis")
        
        if not pending_requests:
            print("✅ All requests already analyzed!")
            return
        
        # Process requests in parallel
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(request, worker_id):
            async with semaphore:
                return await self.analyze_contact_page(request, worker_id)
        
        # Create tasks
        tasks = []
        for i, request in enumerate(pending_requests):
            worker_id = (i % self.max_concurrent) + 1
            task = process_with_semaphore(request, worker_id)
            tasks.append(task)
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_analyses = 0
        failed_analyses = 0
        
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Task failed with exception: {result}")
                failed_analyses += 1
                continue
            
            if result['analysis_success']:
                successful_analyses += 1
                existing_data['request_types'].append(result)
            else:
                failed_analyses += 1
                existing_data['request_types'].append(result)
        
        # Update metadata
        existing_data['metadata'] = {
            "analysis_date": datetime.now().isoformat(),
            "total_request_types": len(successful_requests),
            "successful_analyses": successful_analyses,
            "failed_analyses": failed_analyses,
            "max_concurrent_browsers": self.max_concurrent,
            "headless_mode": self.headless
        }
        
        # Save results
        self.file_locker.write_json(existing_data)
        
        print(f"\n📊 Contact Analysis Summary:")
        print(f"  ✅ Successful: {successful_analyses}")
        print(f"  ❌ Failed: {failed_analyses}")
        print(f"  📁 Results saved to: {self.output_file}")


def print_section_header(title: str, width: int = 80) -> None:
    """Print formatted section header."""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def format_elapsed_time(seconds: float) -> str:
    """Format elapsed time as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


async def main():
    """Main function to run the contact schema analysis."""
    print_section_header("Chicago 311 Contact Schema Analyzer")
    
    start_time = asyncio.get_event_loop().time()
    
    # Configuration
    output_file = Path(__file__).parent.parent / 'data' / 'contact_schemas.json'
    max_concurrent = 3  # Contact info analysis is slower, use fewer browsers
    headless = False  # Set to True for server environments
    slow_mo = 500  # milliseconds, 0 for maximum speed
    
    print(f"Configuration:")
    print(f"  Output file: {output_file}")
    print(f"  Max concurrent browsers: {max_concurrent}")
    print(f"  Headless mode: {headless}")
    print(f"  Slow motion: {slow_mo}ms")
    print("=" * 80)
    
    analyzer = ContactSchemaAnalyzer(
        output_file=output_file,
        max_concurrent=max_concurrent,
        headless=headless,
        slow_mo=slow_mo
    )
    
    try:
        await analyzer.process_all_requests()
    except KeyboardInterrupt:
        print("\n🛑 Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        elapsed_time = asyncio.get_event_loop().time() - start_time
        print(f"\n⏱️ Total elapsed time: {format_elapsed_time(elapsed_time)}")


if __name__ == "__main__":
    asyncio.run(main())
