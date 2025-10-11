#!/usr/bin/env python3
"""
Form Schema Analyzer for Chicago 311 Request Types

Analyzes form field schemas for all Chicago 311 request types using parallel processing.
This script navigates through each request type's form to extract detailed information
about form fields, their types, options, and requirements.
"""

import asyncio
import json
import sys
import fcntl
import os
import signal
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules import AddressHandler


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
class FormField:
    """
    Represents a form field with its properties.
    
    Contains all relevant information about a form field including
    its type, label, options, validation requirements, and interaction methods.
    """
    field_type: str  # 'dropdown', 'textarea', 'text', 'file', 'radio', 'checkbox', 'date', 'unknown', 'multiselect'
    label: str
    name: str
    id: str
    required: bool
    options: List[str] = None  # For dropdown/radio fields
    placeholder: str = None
    maxlength: int = None
    accept: str = None  # For file inputs
    question_number: str = None
    # Additional selectors for reliable form filling
    css_selector: str = None  # Primary CSS selector
    xpath: str = None  # XPath selector
    component_type: str = None  # 'c-search-list', 'lightning-textarea', 'lightning-datepicker', 'lightning-timepicker', etc.
    parent_container: str = None  # Parent container info
    interaction_method: str = None  # 'fill', 'select', 'click', 'upload', 'date', 'multiselect'
    # Special formatting requirements
    date_format: str = None  # For date fields: "Dec 31, 2024", "MM/DD/YYYY", etc.
    input_format: str = None  # General input format requirements
    special_notes: str = None  # Any special instructions for filling this field
    datalist_id: str = None  # For dropdowns: the datalist id attribute value


@dataclass
class FormAnalysis:
    """
    Analysis results for a single request type's form.
    
    Contains comprehensive information about the form structure,
    field types, validation requirements, and any issues found.
    """
    request_id: str
    request_name: str
    category: str
    url: str
    analysis_success: bool
    error_message: str = None
    processing_time_seconds: float = None
    fields: List[FormField] = None
    total_fields: int = 0
    required_fields: int = 0
    optional_fields: int = 0
    field_types_found: List[str] = None
    question_numbering_issues: List[str] = None
    unknown_field_types: List[str] = None
    identical_to_requests: List[str] = None  # Requests with identical form structure


class FormSchemaAnalyzer:
    """
    Analyzes form field schemas for all Chicago 311 request types.
    
    This class handles parallel processing of request types to analyze their
    form structures, extract field information, and identify patterns and issues.
    """
    
    def __init__(self, output_file: Path, max_concurrent: int = 5, 
                 headless: bool = False, slow_mo: int = 500):
        """
        Initialize the form schema analyzer.
        
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
    
    async def analyze_request_form(self, request: Dict[str, Any], worker_id: int) -> Dict[str, Any]:
        """
        Analyze form fields for a single request type.
        
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
                    
                    # Extract form fields
                    fields = await self.extract_form_fields(page, worker_id)
                    
                    # Analyze the extracted fields
                    analysis = self.analyze_fields(fields, request, worker_id)
                    
                    processing_time = asyncio.get_event_loop().time() - start_time
                    analysis.processing_time_seconds = processing_time
                    
                    print(f"✅ [Worker {worker_id}] Completed: {request_name} ({processing_time:.1f}s)")
                    return asdict(analysis)
                    
                except Exception as e:
                    processing_time = asyncio.get_event_loop().time() - start_time
                    print(f"❌ [Worker {worker_id}] Failed: {request_name} - {str(e)}")
                    
                    return {
                        'request_id': request.get('id', ''),
                        'request_name': request_name,
                        'category': request.get('category', ''),
                        'url': request_url,
                        'analysis_success': False,
                        'error_message': str(e),
                        'processing_time_seconds': processing_time,
                        'fields': [],
                        'total_fields': 0,
                        'required_fields': 0,
                        'optional_fields': 0,
                        'field_types_found': [],
                        'question_numbering_issues': [],
                        'unknown_field_types': [],
                        'identical_to_requests': []
                    }
                
                finally:
                    await browser.close()
                    if browser in self.active_browsers:
                        self.active_browsers.remove(browser)
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            print(f"❌ [Worker {worker_id}] Critical error: {request_name} - {str(e)}")
            return {
                'request_id': request.get('id', ''),
                'request_name': request_name,
                'category': request.get('category', ''),
                'url': request_url,
                'analysis_success': False,
                'error_message': f"Critical error: {str(e)}",
                'processing_time_seconds': processing_time,
                'fields': [],
                'total_fields': 0,
                'required_fields': 0,
                'optional_fields': 0,
                'field_types_found': [],
                'question_numbering_issues': [],
                'unknown_field_types': [],
                'identical_to_requests': []
            }
    
    async def extract_form_fields(self, page: Page, worker_id: int) -> List[FormField]:
        """
        Extract all form fields from the current page.
        
        Args:
            page: Playwright page object
            worker_id: ID of the worker for logging
            
        Returns:
            List of FormField objects
        """
        fields = []
        
        print(f"🔍 [Worker {worker_id}] Extracting form fields...")
        
        # Get all form elements
        form_elements = await page.query_selector_all('input, select, textarea, datalist')
        
        for element in form_elements:
            try:
                field = await self.analyze_form_element(element, page)
                if field:
                    fields.append(field)
            except Exception as e:
                print(f"⚠️ [Worker {worker_id}] Error analyzing element: {e}")
                continue
        
        # Also look for custom Lightning components
        custom_fields = await self.extract_custom_components(page, worker_id)
        fields.extend(custom_fields)
        
        print(f"📋 [Worker {worker_id}] Extracted {len(fields)} form fields")
        return fields
    
    async def analyze_form_element(self, element, page: Page) -> Optional[FormField]:
        """
        Analyze a single form element.
        
        Args:
            element: Playwright element handle
            page: Playwright page object
            
        Returns:
            FormField object or None if analysis fails
        """
        tag_name = await element.evaluate('el => el.tagName')
        
        # Get basic attributes
        name = await element.get_attribute('name') or ''
        element_id = await element.get_attribute('id') or ''
        required = await element.get_attribute('required') is not None
        placeholder = await element.get_attribute('placeholder') or ''
        maxlength = await element.get_attribute('maxlength')
        accept = await element.get_attribute('accept') or ''
        
        # Get label
        label = await self.get_element_label(element, element_id, page)
        
        # Determine field type and extract options
        field_type = 'text'
        options = []
        
        if tag_name == 'SELECT':
            field_type = 'dropdown'
            options = await self.extract_select_options(element)
        elif tag_name == 'DATALIST':
            field_type = 'dropdown'
            options = await self.extract_datalist_options(element)
        elif tag_name == 'TEXTAREA':
            field_type = 'textarea'
        elif tag_name == 'INPUT':
            input_type = await element.get_attribute('type') or 'text'
            if input_type == 'file':
                field_type = 'file'
            elif input_type in ['radio', 'checkbox']:
                field_type = input_type
            else:
                field_type = 'text'
        
        # Extract question number from label
        question_number = self.extract_question_number(label)
        
        return FormField(
            field_type=field_type,
            label=label,
            name=name,
            id=element_id,
            required=required,
            options=options if options else None,
            placeholder=placeholder,
            maxlength=int(maxlength) if maxlength else None,
            accept=accept if accept else None,
            question_number=question_number
        )
    
    async def extract_custom_components(self, page: Page, worker_id: int) -> List[FormField]:
        """
        Extract fields from custom Lightning components.
        
        Args:
            page: Playwright page object
            worker_id: ID of the worker for logging
            
        Returns:
            List of FormField objects from custom components
        """
        fields = []
        
        # Look for search-list components (dropdowns with datalist)
        search_lists = await page.query_selector_all('c-search-list')
        for search_list in search_lists:
            try:
                field = await self.analyze_search_list(search_list, page)
                if field:
                    fields.append(field)
            except Exception as e:
                print(f"⚠️ [Worker {worker_id}] Error analyzing search-list: {e}")
                continue
        
        # Look for textarea components
        textareas = await page.query_selector_all('lightning-textarea')
        for textarea in textareas:
            try:
                field = await self.analyze_lightning_textarea(textarea, page)
                if field:
                    fields.append(field)
            except Exception as e:
                print(f"⚠️ [Worker {worker_id}] Error analyzing lightning-textarea: {e}")
                continue
        
        # Look for file upload components
        file_inputs = await page.query_selector_all('lightning-input[type="file"], input[type="file"]')
        for file_input in file_inputs:
            try:
                field = await self.analyze_file_input(file_input, page)
                if field:
                    fields.append(field)
            except Exception as e:
                print(f"⚠️ [Worker {worker_id}] Error analyzing file input: {e}")
                continue
        
        return fields
    
    async def analyze_search_list(self, element, page: Page) -> Optional[FormField]:
        """Analyze a search-list component (dropdown with datalist)."""
        # Get label
        label_elem = await element.query_selector('label.slds-form-element__label')
        label = await label_elem.inner_text() if label_elem else ''
        
        # Get input element
        input_elem = await element.query_selector('input.search-list-input')
        if not input_elem:
            return None
            
        name = await input_elem.get_attribute('name') or ''
        element_id = await input_elem.get_attribute('id') or ''
        required = await input_elem.get_attribute('required') is not None
        
        # Get datalist options
        datalist = await element.query_selector('datalist')
        options = []
        if datalist:
            option_elements = await datalist.query_selector_all('option')
            for option in option_elements:
                value = await option.get_attribute('value')
                if value:
                    options.append(value)
        
        question_number = self.extract_question_number(label)
        
        return FormField(
            field_type='dropdown',
            label=label,
            name=name,
            id=element_id,
            required=required,
            options=options if options else None,
            question_number=question_number
        )
    
    async def analyze_lightning_textarea(self, element, page: Page) -> Optional[FormField]:
        """Analyze a lightning-textarea component."""
        # Get label
        label_elem = await element.query_selector('label')
        label = await label_elem.inner_text() if label_elem else ''
        
        # Get textarea element
        textarea_elem = await element.query_selector('textarea')
        if not textarea_elem:
            return None
            
        name = await textarea_elem.get_attribute('name') or ''
        element_id = await textarea_elem.get_attribute('id') or ''
        maxlength = await textarea_elem.get_attribute('maxlength')
        
        question_number = self.extract_question_number(label)
        
        return FormField(
            field_type='textarea',
            label=label,
            name=name,
            id=element_id,
            required=False,  # Lightning textareas usually don't have required attribute
            maxlength=int(maxlength) if maxlength else None,
            question_number=question_number
        )
    
    async def analyze_file_input(self, element, page: Page) -> Optional[FormField]:
        """Analyze a file input component."""
        # Get label
        label_elem = await element.query_selector('label, .slds-form-element__label')
        label = await label_elem.inner_text() if label_elem else ''
        
        # Get file input element
        file_elem = await element.query_selector('input[type="file"]')
        if not file_elem:
            return None
            
        name = await file_elem.get_attribute('name') or ''
        element_id = await file_elem.get_attribute('id') or ''
        accept = await file_elem.get_attribute('accept') or ''
        
        return FormField(
            field_type='file',
            label=label,
            name=name,
            id=element_id,
            required=False,
            accept=accept if accept else None
        )
    
    async def get_element_label(self, element, element_id: str, page: Page) -> str:
        """Get the label text for a form element."""
        # Try to find label by 'for' attribute
        if element_id:
            label_elem = await page.query_selector(f'label[for="{element_id}"]')
            if label_elem:
                return await label_elem.inner_text()
        
        # Try to find nearby label
        parent = await element.query_selector('xpath=..')
        if parent:
            label_elem = await parent.query_selector('label')
            if label_elem:
                return await label_elem.inner_text()
        
        return ''
    
    async def extract_select_options(self, select_element) -> List[str]:
        """Extract options from a select element."""
        options = []
        option_elements = await select_element.query_selector_all('option')
        for option in option_elements:
            value = await option.get_attribute('value')
            text = await option.inner_text()
            if value and value.strip():
                options.append(value)
            elif text and text.strip():
                options.append(text)
        return options
    
    async def extract_datalist_options(self, datalist_element) -> List[str]:
        """Extract options from a datalist element."""
        options = []
        option_elements = await datalist_element.query_selector_all('option')
        for option in option_elements:
            value = await option.get_attribute('value')
            if value and value.strip():
                options.append(value)
        return options
    
    def extract_question_number(self, label: str) -> Optional[str]:
        """Extract question number from label text."""
        match = re.search(r'(\d+)\.', label)
        return match.group(1) if match else None
    
    def analyze_fields(self, fields: List[FormField], request: Dict[str, Any], worker_id: int) -> FormAnalysis:
        """
        Analyze the extracted fields and create analysis results.
        
        Args:
            fields: List of extracted FormField objects
            request: Original request information
            worker_id: ID of the worker for logging
            
        Returns:
            FormAnalysis object with analysis results
        """
        # Count field types
        field_types = {}
        required_count = 0
        optional_count = 0
        question_numbers = []
        unknown_types = []
        
        for field in fields:
            field_type = field.field_type
            if field_type not in field_types:
                field_types[field_type] = 0
            field_types[field_type] += 1
            
            if field.required:
                required_count += 1
            else:
                optional_count += 1
            
            if field.question_number:
                question_numbers.append(int(field.question_number))
            
            if field_type == 'unknown':
                unknown_types.append(field.label)
        
        # Check for question numbering issues
        question_issues = []
        if question_numbers:
            question_numbers.sort()
            expected = list(range(1, len(question_numbers) + 1))
            if question_numbers != expected:
                missing = set(expected) - set(question_numbers)
                if missing:
                    question_issues.append(f"Missing question numbers: {sorted(missing)}")
        
        return FormAnalysis(
            request_id=request.get('id', ''),
            request_name=request.get('name', ''),
            category=request.get('category', ''),
            url=request.get('url', ''),
            analysis_success=True,
            fields=fields,
            total_fields=len(fields),
            required_fields=required_count,
            optional_fields=optional_count,
            field_types_found=list(field_types.keys()),
            question_numbering_issues=question_issues,
            unknown_field_types=unknown_types,
            identical_to_requests=[]
        )
    
    async def process_all_requests(self) -> None:
        """
        Process all request types in parallel with workers.
        
        Loads request types from the catalog and processes them using
        the specified number of concurrent browser instances.
        """
        print("🚀 Starting Chicago 311 form schema analysis...")
        
        # Load request catalog
        catalog_path = Path(__file__).parent.parent / 'data' / 'request_catalog.json'
        try:
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog_data = json.load(f)
                all_requests = [r for r in catalog_data['chicago_311_request_types']['request_types'] 
                              if r.get('has_create_request_button', False)]
        except Exception as e:
            print(f"❌ Error loading request catalog: {e}")
            return
        
        print(f"📋 Found {len(all_requests)} request types to analyze")
        
        # Load existing results
        existing_data = self.file_locker.read_json()
        existing_requests = {req['request_id']: req for req in existing_data.get('request_types', [])}
        
        # Filter out already processed requests
        pending_requests = []
        for request in all_requests:
            if request.get('id', '') not in existing_requests:
                pending_requests.append(request)
        
        print(f"📝 {len(pending_requests)} requests pending analysis")
        
        if not pending_requests:
            print("✅ All requests already analyzed!")
            self.print_statistics(existing_data)
            return
        
        # Process requests in parallel
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(request, worker_id):
            async with semaphore:
                return await self.analyze_request_form(request, worker_id)
        
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
            "total_request_types": len(all_requests),
            "successful_analyses": successful_analyses,
            "failed_analyses": failed_analyses,
            "max_concurrent_browsers": self.max_concurrent,
            "headless_mode": self.headless
        }
        
        # Save results
        self.file_locker.write_json(existing_data)
        
        print(f"\n📊 Analysis Summary:")
        print(f"  ✅ Successful: {successful_analyses}")
        print(f"  ❌ Failed: {failed_analyses}")
        print(f"  📁 Results saved to: {self.output_file}")
        
        # Print detailed statistics
        self.print_statistics(existing_data)
    
    def print_statistics(self, results: Dict[str, Any]) -> None:
        """
        Print analysis statistics and findings.
        
        Args:
            results: Dictionary containing analysis results
        """
        request_types = results.get('request_types', [])
        successful_requests = [r for r in request_types if r.get('analysis_success', False)]
        
        print(f"\n📈 Detailed Statistics:")
        print(f"  Total analyzed: {len(request_types)}")
        print(f"  Successful: {len(successful_requests)}")
        print(f"  Failed: {len(request_types) - len(successful_requests)}")
        
        if successful_requests:
            # Field type statistics
            all_field_types = {}
            total_fields = 0
            total_required = 0
            
            for request in successful_requests:
                fields = request.get('fields', [])
                total_fields += len(fields)
                total_required += request.get('required_fields', 0)
                
                for field_type in request.get('field_types_found', []):
                    all_field_types[field_type] = all_field_types.get(field_type, 0) + 1
            
            print(f"\n📋 Field Type Distribution:")
            for field_type, count in sorted(all_field_types.items()):
                print(f"  {field_type}: {count} requests")
            
            print(f"\n📊 Field Statistics:")
            print(f"  Total fields: {total_fields}")
            print(f"  Required fields: {total_required}")
            print(f"  Optional fields: {total_fields - total_required}")
            
            # Question numbering issues
            requests_with_issues = [r for r in successful_requests 
                                  if r.get('question_numbering_issues')]
            if requests_with_issues:
                print(f"\n⚠️ Question Numbering Issues ({len(requests_with_issues)} requests):")
                for request in requests_with_issues[:5]:  # Show first 5
                    print(f"  {request['request_name']}: {request['question_numbering_issues']}")
            
            # Unknown field types
            requests_with_unknown = [r for r in successful_requests 
                                   if r.get('unknown_field_types')]
            if requests_with_unknown:
                print(f"\n❓ Unknown Field Types ({len(requests_with_unknown)} requests):")
                for request in requests_with_unknown[:5]:  # Show first 5
                    print(f"  {request['request_name']}: {request['unknown_field_types']}")


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
    """Main function to run the form schema analysis."""
    print_section_header("Chicago 311 Form Schema Analyzer")
    
    start_time = asyncio.get_event_loop().time()
    
    # Configuration
    output_file = Path(__file__).parent.parent / 'data' / 'form_schemas.json'
    max_concurrent = 5  # Number of concurrent browsers
    headless = False  # Set to True for server environments
    slow_mo = 500  # milliseconds, 0 for maximum speed
    
    print(f"Configuration:")
    print(f"  Output file: {output_file}")
    print(f"  Max concurrent browsers: {max_concurrent}")
    print(f"  Headless mode: {headless}")
    print(f"  Slow motion: {slow_mo}ms")
    print("=" * 80)
    
    analyzer = FormSchemaAnalyzer(
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
