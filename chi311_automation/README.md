# Chicago 311 Automation System

A comprehensive automation system for analyzing and interacting with Chicago 311 service request forms. This system provides tools to extract form schemas, analyze contact information pages, and automate the complete workflow from address input to form submission.

## Table of Contents

- [Overview](#overview)
- [Installation & Setup](#installation--setup)
- [Directory Structure](#directory-structure)
- [Modules Reference](#modules-reference)
- [Scripts Reference](#scripts-reference)
- [Data Files](#data-files)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Overview

The Chicago 311 Automation System is designed to:

- **Extract URLs** for all 106 Chicago 311 request types
- **Analyze form schemas** to understand field types, requirements, and validation rules
- **Analyze contact information pages** to identify standard and unique fields
- **Automate form filling** with support for all field types (dropdowns, multiselects, dates, times, etc.)
- **Test complete workflows** from address input to final submission

### Key Features

- ✅ **Class-based Architecture**: Clean, maintainable code with reusable components
- ✅ **Parallel Processing**: Fast analysis using multiple browser instances
- ✅ **Comprehensive Field Support**: Handles all Salesforce Lightning components
- ✅ **Robust Error Handling**: Graceful failure recovery and detailed logging
- ✅ **File Locking**: Thread-safe operations for concurrent processing
- ✅ **Progress Tracking**: Resume interrupted operations automatically
- ✅ **Type Safety**: Full type hints and validation

## Installation & Setup

### Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager
- Chrome/Chromium browser

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd chi311-mcp-server

# Install dependencies
uv sync

# Verify installation
uv run python -c "from chi311_automation.modules import AddressHandler, FormHandler, ContactHandler; print('✅ Installation successful')"
```

## Directory Structure

```
chi311_automation/
├── modules/              # Reusable automation modules
│   ├── __init__.py
│   ├── config.py        # Configuration constants
│   ├── base_handler.py  # Base class for all handlers
│   ├── address_handler.py    # Address setup automation
│   ├── form_handler.py       # Form field filling
│   └── contact_handler.py    # Contact info filling
├── data/                # JSON data files
│   ├── request_catalog.json   # All 106 request types
│   ├── form_schemas.json      # Form field schemas
│   └── contact_schemas.json   # Contact field schemas
└── scripts/             # Executable scripts
    ├── extract_request_urls.py      # URL extraction
    ├── analyze_form_schemas.py      # Form analysis
    ├── analyze_contact_schemas.py   # Contact analysis
    └── test_complete_workflow.py    # Integration test
```

## Modules Reference

### config.py

Centralized configuration module containing all timeouts, selectors, and settings.

**Key Constants:**
- `ELEMENT_TIMEOUT`: Default timeout for element interactions (2000ms)
- `FIELD_INTERACTION_WAIT`: Delay between field interactions (100ms)
- `NEXT_BUTTON_SELECTOR`: Precise selector for Next buttons
- `SUBMIT_BUTTON_SELECTOR`: Precise selector for Submit buttons
- `VERBOSE`: Enable detailed logging

**Usage:**
```python
from chi311_automation.modules.config import ELEMENT_TIMEOUT, VERBOSE
```

### base_handler.py

Base class providing common functionality for all automation handlers.

**Key Methods:**
- `_wait_for_element()`: Wait for element with timeout
- `_click_element()`: Click element with error handling
- `_fill_element()`: Fill input with validation
- `_try_selectors()`: Try multiple selectors until one works
- `_log_operation()`: Consistent logging across handlers

**Usage:**
```python
from chi311_automation.modules.base_handler import BaseHandler

class MyHandler(BaseHandler):
    def __init__(self, page):
        super().__init__(page)
    
    async def my_method(self):
        element = await self._wait_for_element('button')
        await self._click_element(element)
```

### address_handler.py (AddressHandler)

Handles address input and confirmation for Chicago 311 forms.

**Key Methods:**
- `setup()`: Complete address setup process
- `setup_with_retry()`: Setup with retry logic
- `verify_setup()`: Verify address was set correctly

**Usage:**
```python
from chi311_automation.modules import AddressHandler

address_handler = AddressHandler(page)
success = await address_handler.setup()
if success:
    print("Address setup completed")
```

### form_handler.py (FormHandler)

Handles filling all types of form fields and navigation.

**Supported Field Types:**
- `dropdown`: Standard dropdowns with datalist
- `multiselect`: Dual-listbox components
- `date`: Date picker fields
- `time`: Time picker fields
- `number`: Number input fields
- `text`: Text input fields
- `textarea`: Multi-line text areas
- `file`: File upload fields

**Key Methods:**
- `fill_form()`: Fill entire form with data
- `fill_field()`: Fill individual field
- `click_next()`: Navigate to next page

**Usage:**
```python
from chi311_automation.modules import FormHandler

form_handler = FormHandler(page)
form_data = {
    "1. What is your issue?": "Sample text",
    "2. Select options": ["Option 1", "Option 3"],
    "3. Date": "Dec 15, 2024"
}
results = await form_handler.fill_form(fields, form_data)
print(f"Filled: {results['filled']}, Failed: {results['failed']}")
```

### contact_handler.py (ContactHandler)

Handles contact information page filling and submission.

**Key Methods:**
- `detect_fields()`: Detect all contact fields on page
- `fill_contact_info()`: Fill contact information
- `click_submit()`: Submit the form

**Usage:**
```python
from chi311_automation.modules import ContactHandler

contact_handler = ContactHandler(page)
contact_data = {
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john@example.com',
    'phone': '312-555-0123',
    'street_address': '123 Main St',
    'city': 'Chicago',
    'state': 'IL',
    'postal_code': '60601',
    'country': 'United States',
    'anonymous': False
}
results = await contact_handler.fill_contact_info(contact_data)
```

## Scripts Reference

### extract_request_urls.py (RequestUrlExtractor)

Extracts CREATE REQUEST URLs for all Chicago 311 request types from the portal.

**Features:**
- Parallel processing with configurable concurrency
- Progress tracking and resume capability
- Graceful shutdown on Ctrl+C
- Atomic file operations

**Usage:**
```bash
# Basic usage
uv run python chi311_automation/scripts/extract_request_urls.py

# With custom configuration
python -c "
from chi311_automation.scripts.extract_request_urls import RequestUrlExtractor
import asyncio

async def main():
    extractor = RequestUrlExtractor(
        output_file='custom_urls.json',
        max_concurrent=5
    )
    await extractor.process_all_requests()

asyncio.run(main())
"
```

**Output:** `311_urls_extraction.json` with all request URLs

### analyze_form_schemas.py (FormSchemaAnalyzer)

Analyzes form field schemas for all Chicago 311 request types.

**Features:**
- Parallel workers with file locking
- Comprehensive field type detection
- Question numbering validation
- Unknown field type flagging
- Identical form structure detection

**Usage:**
```bash
# Basic usage
uv run python chi311_automation/scripts/analyze_form_schemas.py

# With custom configuration
python -c "
from chi311_automation.scripts.analyze_form_schemas import FormSchemaAnalyzer
from pathlib import Path
import asyncio

async def main():
    analyzer = FormSchemaAnalyzer(
        output_file=Path('custom_schemas.json'),
        max_concurrent=10,
        headless=True,
        slow_mo=0
    )
    await analyzer.process_all_requests()

asyncio.run(main())
"
```

**Output:** `form_schemas.json` with complete field schemas

### analyze_contact_schemas.py (ContactSchemaAnalyzer)

Analyzes contact information page schemas for all request types.

**Features:**
- Parallel processing with form filling
- Contact field type detection
- Anonymous option detection
- Unique field identification
- Standard field validation

**Usage:**
```bash
# Basic usage
uv run python chi311_automation/scripts/analyze_contact_schemas.py

# With custom configuration
python -c "
from chi311_automation.scripts.analyze_contact_schemas import ContactSchemaAnalyzer
from pathlib import Path
import asyncio

async def main():
    analyzer = ContactSchemaAnalyzer(
        output_file=Path('custom_contact.json'),
        max_concurrent=3,
        headless=False,
        slow_mo=500
    )
    await analyzer.process_all_requests()

asyncio.run(main())
"
```

**Output:** `contact_schemas.json` with contact field schemas

### test_complete_workflow.py

Integration test for the complete automation workflow.

**Test Steps:**
1. Navigate to form
2. Setup address (if required)
3. Fill form fields
4. Navigate to contact page
5. Fill contact information
6. Submit form

**Usage:**
```bash
# Run complete workflow test
uv run python chi311_automation/scripts/test_complete_workflow.py

# Test specific request type
python -c "
from chi311_automation.scripts.test_complete_workflow import test_complete_workflow
import asyncio

asyncio.run(test_complete_workflow())
"
```

## Data Files

### request_catalog.json

Contains the complete catalog of all 106 Chicago 311 request types.

**Structure:**
```json
{
  "chicago_311_request_types": {
    "request_types": [
      {
        "id": "abandoned_vehicle_complaint",
        "name": "Abandoned Vehicle Complaint",
        "category": "Public Safety",
        "url": "https://311.chicago.gov/s/...",
        "has_create_request_button": true
      }
    ]
  }
}
```

### form_schemas.json

Complete form field schemas for all request types.

**Structure:**
```json
{
  "metadata": {
    "analysis_date": "2024-10-10T...",
    "total_request_types": 106,
    "successful_analyses": 105
  },
  "request_types": [
    {
      "request_id": "abandoned_vehicle_complaint",
      "request_name": "Abandoned Vehicle Complaint",
      "analysis_success": true,
      "total_fields": 8,
      "fields": [
        {
          "field_type": "dropdown",
          "label": "1. Vehicle Type:",
          "required": true,
          "options": ["Car", "Truck", "Motorcycle"],
          "css_selector": "input.search-list-input",
          "component_type": "c-search-list"
        }
      ]
    }
  ]
}
```

### contact_schemas.json

Contact information page schemas for all request types.

**Structure:**
```json
{
  "metadata": {
    "analysis_date": "2024-10-10T...",
    "total_request_types": 106,
    "successful_analyses": 105
  },
  "request_types": [
    {
      "request_id": "abandoned_vehicle_complaint",
      "request_name": "Abandoned Vehicle Complaint",
      "analysis_success": true,
      "total_fields": 9,
      "anonymous_option_available": true,
      "fields": [
        {
          "field_type": "text",
          "label": "First Name",
          "name": "firstname",
          "required": true,
          "component_type": "lightning-input"
        }
      ]
    }
  ]
}
```

## Usage Examples

### Quick Start

#### Example 1: Fill a Single Form

```python
import asyncio
from playwright.async_api import async_playwright
from chi311_automation.modules import AddressHandler, FormHandler, ContactHandler

async def fill_single_form():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to form
        await page.goto("https://311.chicago.gov/s/...")
        
        # Setup address
        address_handler = AddressHandler(page)
        await address_handler.setup()
        
        # Fill form
        form_handler = FormHandler(page)
        form_data = {"1. Issue": "Sample text"}
        await form_handler.fill_form(fields, form_data)
        await form_handler.click_next()
        
        # Fill contact info
        contact_handler = ContactHandler(page)
        contact_data = {"first_name": "John", "email": "john@example.com"}
        await contact_handler.fill_contact_info(contact_data)
        await contact_handler.click_submit()
        
        await browser.close()

asyncio.run(fill_single_form())
```

#### Example 2: Analyze All Forms

```python
from chi311_automation.scripts.analyze_form_schemas import FormSchemaAnalyzer
from pathlib import Path

async def analyze_all_forms():
    analyzer = FormSchemaAnalyzer(
        output_file=Path('my_analysis.json'),
        max_concurrent=5,
        headless=True
    )
    await analyzer.process_all_requests()

asyncio.run(analyze_all_forms())
```

#### Example 3: Complete Workflow Test

```python
from chi311_automation.scripts.test_complete_workflow import test_complete_workflow

# Run the complete integration test
asyncio.run(test_complete_workflow())
```

### Common Tasks

#### Running Analysis Scripts

```bash
# Extract all URLs
uv run python chi311_automation/scripts/extract_request_urls.py

# Analyze form schemas
uv run python chi311_automation/scripts/analyze_form_schemas.py

# Analyze contact schemas
uv run python chi311_automation/scripts/analyze_contact_schemas.py
```

#### Testing Automation

```bash
# Run complete workflow test
uv run python chi311_automation/scripts/test_complete_workflow.py
```

#### Debugging Issues

```python
# Enable verbose logging
from chi311_automation.modules.config import VERBOSE
VERBOSE = True

# Use headless=False for visual debugging
analyzer = FormSchemaAnalyzer(headless=False, slow_mo=1000)
```

## Configuration

### Timeout Settings

```python
# In config.py
ELEMENT_TIMEOUT = 2000        # Element wait timeout (ms)
FIELD_INTERACTION_WAIT = 100  # Delay between field interactions (ms)
NEXT_BUTTON_WAIT = 2000       # Wait after clicking Next (ms)
CONTACT_PAGE_LOAD_WAIT = 3000 # Wait for contact page load (ms)
```

### Browser Settings

```python
# In analyzer classes
headless = False    # Show browser window (True for servers)
slow_mo = 500       # Delay between actions (0 for maximum speed)
max_concurrent = 5  # Number of parallel browsers
```

### Selector Customization

```python
# In config.py
NEXT_BUTTON_SELECTOR = 'button.slds-button.slds-button_brand.sfdc_button[data-aura-rendered-by]:has-text("next")'
SUBMIT_BUTTON_SELECTOR = 'button.slds-button.slds-button_brand.sfdc_button[data-aura-rendered-by]:has-text("next")'
```

## API Reference

### AddressHandler

```python
class AddressHandler(BaseHandler):
    async def setup(self, address: str = "123 Main St, Chicago, IL", 
                   apt_suite: str = "Apt 1B") -> bool
    async def setup_with_retry(self, max_retries: int = 3) -> bool
    async def verify_setup(self) -> bool
```

### FormHandler

```python
class FormHandler(BaseHandler):
    async def fill_form(self, fields: List[Dict], data: Dict[str, Any]) -> Dict[str, int]
    async def fill_field(self, field: Dict, value: Any) -> bool
    async def click_next(self) -> bool
```

### ContactHandler

```python
class ContactHandler(BaseHandler):
    async def detect_fields(self) -> Dict[str, ContactField]
    async def fill_contact_info(self, data: Dict[str, Any]) -> Dict[str, int]
    async def click_submit(self) -> bool
```

### Analyzer Classes

```python
class FormSchemaAnalyzer:
    def __init__(self, output_file: Path, max_concurrent: int = 5, 
                 headless: bool = False, slow_mo: int = 500)
    async def process_all_requests(self) -> None
    def print_statistics(self, results: Dict[str, Any]) -> None

class ContactSchemaAnalyzer:
    def __init__(self, output_file: Path, max_concurrent: int = 3, 
                 headless: bool = False, slow_mo: int = 500)
    async def process_all_requests(self) -> None

class RequestUrlExtractor:
    def __init__(self, output_file: str = "311_urls_extraction.json", 
                 max_concurrent: int = 3)
    async def process_all_requests(self) -> None
```

## Troubleshooting

### Common Issues

#### Browser Not Closing

```bash
# Kill all Chromium processes
pkill -f chromium

# Or restart the script
uv run python chi311_automation/scripts/analyze_form_schemas.py
```

#### Timeout Errors

```python
# Increase timeouts in config.py
ELEMENT_TIMEOUT = 5000  # Increase from 2000
FIELD_INTERACTION_WAIT = 200  # Increase from 100
```

#### Field Not Found

```python
# Enable verbose logging to see selector attempts
from chi311_automation.modules.config import VERBOSE
VERBOSE = True

# Check if selectors need updating
# Update selectors in config.py based on page changes
```

#### Re-running Failed Analyses

```python
# Mark specific requests as failed in JSON
# Set analysis_success: false for failed requests
# Re-run the analyzer - it will only process failed ones
```

### Performance Optimization

#### For Faster Analysis

```python
# Use more concurrent browsers
analyzer = FormSchemaAnalyzer(max_concurrent=10)

# Enable headless mode
analyzer = FormSchemaAnalyzer(headless=True)

# Disable slow motion
analyzer = FormSchemaAnalyzer(slow_mo=0)
```

#### For Debugging

```python
# Use fewer browsers for easier debugging
analyzer = FormSchemaAnalyzer(max_concurrent=1)

# Enable visual mode
analyzer = FormSchemaAnalyzer(headless=False, slow_mo=1000)

# Enable verbose logging
VERBOSE = True
```

## Contributing

### Adding New Field Types

1. **Update FormHandler** in `form_handler.py`:
```python
async def fill_field(self, field: Dict, value: Any) -> bool:
    field_type = field.get('field_type')
    
    if field_type == 'new_field_type':
        return await self._fill_new_field_type(field, value)
    # ... existing code
```

2. **Add detection logic** in analyzer classes
3. **Update documentation** and tests

### Extending Handlers

1. **Inherit from BaseHandler**:
```python
from chi311_automation.modules.base_handler import BaseHandler

class MyHandler(BaseHandler):
    def __init__(self, page):
        super().__init__(page)
    
    async def my_method(self):
        # Use inherited methods
        element = await self._wait_for_element('selector')
        await self._click_element(element)
```

### Customizing Selectors

1. **Update config.py** with new selectors
2. **Test with verbose logging** enabled
3. **Update documentation** with new selectors

### Testing Procedures

1. **Run integration test**:
```bash
uv run python chi311_automation/scripts/test_complete_workflow.py
```

2. **Test individual modules**:
```python
from chi311_automation.modules import AddressHandler, FormHandler, ContactHandler
# Test each handler individually
```

3. **Run analysis scripts**:
```bash
uv run python chi311_automation/scripts/analyze_form_schemas.py
uv run python chi311_automation/scripts/analyze_contact_schemas.py
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [API Reference](#api-reference)
3. Open an issue on GitHub