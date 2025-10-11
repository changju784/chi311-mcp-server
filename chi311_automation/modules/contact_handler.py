#!/usr/bin/env python3
"""
Contact handler module for Chicago 311 forms.
This module provides universal contact information filling functionality.
"""

import logging
from playwright.async_api import Page
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .base_handler import BaseHandler
from .config import (
    FIELD_INTERACTION_WAIT,
    ELEMENT_TIMEOUT,
    CONTACT_FIELD_SELECTORS,
    SUBMIT_BUTTON_SELECTOR,
    NEXT_BUTTON_WAIT,
    VERBOSE
)


@dataclass
class ContactField:
    """
    Contact field information.
    
    Attributes:
        field_type: Type of field (text, email, phone, etc.)
        label: Human-readable field label
        name: HTML element name attribute
        id: HTML element ID
        required: Whether the field is required
        placeholder: Field placeholder text
        maxlength: Maximum input length
        pattern: Input validation pattern
        input_type: HTML input type
        options: Available options for select fields
        css_selector: CSS selector for the field
        xpath: XPath selector for the field
        component_type: Salesforce Lightning component type
        special_notes: Additional notes about the field
        validation_rules: Field validation rules
    """
    field_type: str
    label: str
    name: str
    id: str
    required: bool
    placeholder: str = None
    maxlength: int = None
    pattern: str = None
    input_type: str = None
    options: List[str] = None
    css_selector: str = None
    xpath: str = None
    component_type: str = None
    special_notes: str = None
    validation_rules: str = None


class ContactHandler(BaseHandler):
    """
    Handler for Chicago 311 contact information page.
    
    This class detects and fills standard contact information fields on the "who" page
    of Chicago 311 forms. It handles various field types including text, email, phone,
    dropdown, and checkbox fields.
    
    Example:
        contact_handler = ContactHandler(page)
        fields = await contact_handler.detect_fields()
        result = await contact_handler.fill_contact_info({
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone': '312-555-0123'
        })
    """
    
    # Standard contact field patterns
    STANDARD_CONTACT_FIELDS = {
        'first_name': {
            'patterns': ['first name', 'firstname', 'fname', 'given name'],
            'field_types': ['text']
        },
        'last_name': {
            'patterns': ['last name', 'lastname', 'lname', 'surname', 'family name'],
            'field_types': ['text']
        },
        'street_address': {
            'patterns': ['street address', 'address', 'street', 'street addr', 'mailing address'],
            'field_types': ['text', 'textarea']
        },
        'city': {
            'patterns': ['city', 'municipality'],
            'field_types': ['text']
        },
        'state': {
            'patterns': ['state', 'province'],
            'field_types': ['text']
        },
        'postal_code': {
            'patterns': ['postal code', 'zip code', 'zip', 'postal', 'postcode'],
            'field_types': ['text']
        },
        'country': {
            'patterns': ['country', 'nation'],
            'field_types': ['text']
        },
        'email': {
            'patterns': ['email', 'e-mail', 'email address'],
            'field_types': ['email', 'text']
        },
        'phone': {
            'patterns': ['phone', 'telephone', 'phone number', 'mobile', 'cell'],
            'field_types': ['tel', 'text']
        },
        'anonymous': {
            'patterns': ['anonymous', 'remain anonymous', 'submit anonymously'],
            'field_types': ['checkbox']
        }
    }
    
    def __init__(self, page: Page):
        """
        Initialize the contact handler.
        
        Args:
            page: Playwright page object
        """
        super().__init__(page)
        self.detected_fields: Dict[str, ContactField] = {}
    
    async def detect_fields(self) -> Dict[str, ContactField]:
        """
        Detect all contact fields on the page and map them to standard field types.
        
        Returns:
            Dict mapping standard field types to ContactField objects
        """
        self.logger.info("Detecting contact information fields...")
        
        all_fields = []
        
        # Extract standard HTML fields
        for selector in CONTACT_FIELD_SELECTORS:
            elements = await self.page.query_selector_all(selector)
            for element in elements:
                field = await self._extract_field_metadata(element)
                if field and field.label.strip():
                    all_fields.append(field)
        
        # Extract Lightning components (for anonymous toggle)
        lightning_fields = await self._extract_lightning_fields()
        all_fields.extend(lightning_fields)
        
        # Remove duplicates
        seen_fields = set()
        unique_fields = []
        for field in all_fields:
            field_key = f"{field.id}_{field.name}_{field.label}"
            if field_key not in seen_fields:
                unique_fields.append(field)
                seen_fields.add(field_key)
        
        # Map fields to standard types
        self.detected_fields = await self._map_to_standard_fields(unique_fields)
        
        self.logger.info(f"Detected {len(unique_fields)} contact fields, mapped to {len(self.detected_fields)} standard types")
        if VERBOSE:
            for field_type, field in self.detected_fields.items():
                self.logger.debug(f"{field_type}: {field.label} (ID: {field.id}, Name: {field.name})")
        return self.detected_fields
    
    async def _extract_field_metadata(self, element) -> Optional[ContactField]:
        """Extract metadata from a single contact field element."""
        try:
            # Get basic attributes
            field_id = await element.get_attribute('id') or ''
            field_name = await element.get_attribute('name') or ''
            field_type = await element.get_attribute('type') or 'text'
            placeholder = await element.get_attribute('placeholder') or ''
            maxlength = await element.get_attribute('maxlength')
            pattern = await element.get_attribute('pattern') or ''
            inputmode = await element.get_attribute('inputmode') or ''
            
            # Get label
            label = await self._get_field_label(element, field_id, field_name)
            
            # Determine if required
            required = await element.get_attribute('required') is not None
            
            # Get CSS selector
            css_selector = f'input[name="{field_name}"]' if field_name else f'input[id="{field_id}"]'
            
            return ContactField(
                field_type=field_type,
                label=label,
                name=field_name,
                id=field_id,
                required=required,
                placeholder=placeholder,
                maxlength=int(maxlength) if maxlength else None,
                pattern=pattern,
                input_type=field_type,
                options=None,
                css_selector=css_selector,
                xpath=None,
                component_type='standard',
                special_notes=f'Input mode: {inputmode}' if inputmode else None,
                validation_rules=pattern
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing contact field: {e}")
            return None
    
    async def _extract_lightning_fields(self) -> List[ContactField]:
        """Extract Lightning component contact fields."""
        fields = []
        
        # Lightning input components
        lightning_inputs = await self.page.query_selector_all('lightning-input')
        for element in lightning_inputs:
            field = await self._analyze_lightning_input(element)
            if field and field.label.strip():
                fields.append(field)
        
        # Lightning combobox components
        lightning_comboboxes = await self.page.query_selector_all('lightning-combobox')
        for element in lightning_comboboxes:
            field = await self._analyze_lightning_combobox(element)
            if field and field.label.strip():
                fields.append(field)
        
        # Lightning textarea components
        lightning_textareas = await self.page.query_selector_all('lightning-textarea')
        for element in lightning_textareas:
            field = await self._analyze_lightning_textarea(element)
            if field and field.label.strip():
                fields.append(field)
        
        return fields
    
    async def _analyze_lightning_input(self, element) -> Optional[ContactField]:
        """Analyze a lightning-input component."""
        try:
            # Get basic attributes
            field_id = await element.get_attribute('data-field-id') or ''
            field_name = await element.get_attribute('name') or ''
            field_type = await element.get_attribute('type') or 'text'
            placeholder = await element.get_attribute('placeholder') or ''
            maxlength = await element.get_attribute('maxlength')
            pattern = await element.get_attribute('pattern') or ''
            inputmode = await element.get_attribute('inputmode') or ''
            
            # Get label
            label = await self._get_field_label(element, field_id, field_name)
            
            # Determine if required
            required = await element.get_attribute('required') is not None
            
            # Get CSS selector
            css_selector = f'lightning-input[name="{field_name}"]' if field_name else f'lightning-input[data-field-id="{field_id}"]'
            
            # Special notes
            special_notes = []
            if inputmode:
                special_notes.append(f'Input mode: {inputmode}')
            if pattern:
                special_notes.append(f'Pattern: {pattern}')
            
            return ContactField(
                field_type=field_type,
                label=label,
                name=field_name,
                id=field_id,
                required=required,
                placeholder=placeholder,
                maxlength=int(maxlength) if maxlength else None,
                pattern=pattern,
                input_type=field_type,
                options=None,
                css_selector=css_selector,
                xpath=None,
                component_type='lightning-input',
                special_notes='; '.join(special_notes) if special_notes else None,
                validation_rules=pattern
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing lightning input: {e}")
            return None
    
    async def _analyze_lightning_combobox(self, element) -> Optional[ContactField]:
        """Analyze a lightning-combobox component."""
        try:
            # Get basic attributes
            field_id = await element.get_attribute('data-field-id') or ''
            field_name = await element.get_attribute('name') or ''
            placeholder = await element.get_attribute('placeholder') or ''
            
            # Get label
            label = await self._get_field_label(element, field_id, field_name)
            
            # Determine if required
            required = await element.get_attribute('required') is not None
            
            # Get options
            options = []
            option_elements = await element.query_selector_all('option')
            for option in option_elements:
                option_text = await option.inner_text()
                if option_text.strip():
                    options.append(option_text.strip())
            
            # Get CSS selector
            css_selector = f'lightning-combobox[name="{field_name}"]' if field_name else f'lightning-combobox[data-field-id="{field_id}"]'
            
            return ContactField(
                field_type='dropdown',
                label=label,
                name=field_name,
                id=field_id,
                required=required,
                placeholder=placeholder,
                maxlength=None,
                pattern=None,
                input_type='dropdown',
                options=options,
                css_selector=css_selector,
                xpath=None,
                component_type='lightning-combobox',
                special_notes=None
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing lightning combobox: {e}")
            return None
    
    async def _analyze_lightning_textarea(self, element) -> Optional[ContactField]:
        """Analyze a lightning-textarea component."""
        try:
            # Get basic attributes
            field_id = await element.get_attribute('data-field-id') or ''
            field_name = await element.get_attribute('name') or ''
            placeholder = await element.get_attribute('placeholder') or ''
            maxlength = await element.get_attribute('maxlength')
            
            # Get label
            label = await self._get_field_label(element, field_id, field_name)
            
            # Determine if required
            required = await element.get_attribute('required') is not None
            
            # Get CSS selector
            css_selector = f'lightning-textarea[name="{field_name}"]' if field_name else f'lightning-textarea[data-field-id="{field_id}"]'
            
            return ContactField(
                field_type='textarea',
                label=label,
                name=field_name,
                id=field_id,
                required=required,
                placeholder=placeholder,
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
            self.logger.error(f"Error analyzing lightning textarea: {e}")
            return None
    
    async def _get_field_label(self, element, field_id: str, field_name: str) -> str:
        """Get field label using multiple strategies."""
        try:
            # Strategy 1: Look for label with for attribute
            if field_id:
                label_elem = await self.page.query_selector(f'label[for="{field_id}"]')
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
                label_elem = await self.page.query_selector(f'#{labelledby}')
                if label_elem:
                    return await label_elem.inner_text()
            
            # Strategy 4: Look for aria-label
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                return aria_label
            
            # Strategy 5: Look for placeholder
            placeholder = await element.get_attribute('placeholder')
            if placeholder:
                return placeholder
            
            # Strategy 6: Map field names to labels for contact info page
            field_name_mapping = {
                'firstname': 'First Name',
                'lastname': 'Last Name',
                'address': 'Street Address',
                'city': 'City',
                'state': 'State',
                'postalcode': 'Postal Code',
                'country': 'Country',
                'email': 'Email',
                'phone': 'Phone',
                'submitAnonymously': 'I wish to remain anonymous'
            }
            
            if field_name in field_name_mapping:
                return field_name_mapping[field_name]
            
            return f"Field {field_id or field_name or 'Unknown'}"
            
        except Exception as e:
            return f"Field {field_id or field_name or 'Unknown'}"
    
    async def _map_to_standard_fields(self, fields: List[ContactField]) -> Dict[str, ContactField]:
        """Map detected fields to standard contact field types."""
        mapped_fields = {}
        
        # Direct name mapping for contact info fields
        name_mapping = {
            'firstname': 'first_name',
            'lastname': 'last_name',
            'address': 'street_address',
            'city': 'city',
            'state': 'state',
            'postalcode': 'postal_code',
            'country': 'country',
            'email': 'email',
            'phone': 'phone',
            'submitAnonymously': 'anonymous'
        }
        
        for field in fields:
            field_name = field.name.lower()
            field_type = field.field_type.lower()
            label_lower = field.label.lower()
            
            # Try direct name mapping first
            if field_name in name_mapping:
                standard_type = name_mapping[field_name]
                if standard_type not in mapped_fields:  # Only map if not already mapped
                    mapped_fields[standard_type] = field
                    if VERBOSE:
                        self.logger.debug(f"Mapped by name: {field_name} -> {standard_type}")
                    continue
            
            # Try to match to standard field types by label patterns
            for standard_type, config in self.STANDARD_CONTACT_FIELDS.items():
                if standard_type in mapped_fields:  # Skip if already mapped
                    continue
                
                # Check patterns
                for pattern in config['patterns']:
                    if pattern in label_lower:
                        mapped_fields[standard_type] = field
                        if VERBOSE:
                            self.logger.debug(f"Mapped by pattern: {pattern} -> {standard_type}")
                        break
                
                if standard_type in mapped_fields:
                    break
                
                # Check field types
                if field_type in config['field_types']:
                    mapped_fields[standard_type] = field
                    if VERBOSE:
                        self.logger.debug(f"Mapped by type: {field_type} -> {standard_type}")
                    break
        
        return mapped_fields
    
    async def fill_contact_info(self, contact_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Fill contact information page with provided data.
        
        Args:
            contact_data: Dictionary mapping standard field types to values
            
        Returns:
            Dict with counts of filled, failed, and skipped fields
        """
        self.logger.info("Filling contact information")
        
        # Detect fields if not already done
        if not self.detected_fields:
            await self.detect_fields()
        
        filled_count = 0
        failed_count = 0
        skipped_count = 0
        
        for standard_type, value in contact_data.items():
            if standard_type in self.detected_fields:
                field = self.detected_fields[standard_type]
                if VERBOSE:
                    self.logger.debug(f"Filling {standard_type}: '{value}'")
                
                if await self._fill_field(field, value):
                    filled_count += 1
                else:
                    self.logger.error(f"Failed to fill {standard_type}")
                    failed_count += 1
            else:
                if VERBOSE:
                    self.logger.debug(f"No field found for {standard_type}")
                skipped_count += 1
        
        self.logger.info("Contact info filling results:")
        self.logger.info(f"Successfully filled: {filled_count}")
        self.logger.info(f"Failed to fill: {failed_count}")
        self.logger.info(f"Skipped (no field): {skipped_count}")
        
        return {
            "filled_count": filled_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count
        }
    
    async def _fill_field(self, field: ContactField, value: Any) -> bool:
        """Fill a single field with the provided value."""
        try:
            # Handle different field types
            if field.field_type == 'checkbox':
                # For anonymous checkbox
                if value is True:
                    # Try multiple selectors for the checkbox
                    checkbox_selectors = [
                        f'input[name="{field.name}"]',
                        f'input[id="{field.id}"]',
                        'input[type="checkbox"][name="submitAnonymously"]',
                        'input[id*="checkbox-toggle"]'
                    ]
                    
                    for selector in checkbox_selectors:
                        try:
                            element = await self.page.query_selector(selector)
                            if element:
                                await element.click()
                                if VERBOSE:
                                    self.logger.debug(f"Checkbox clicked with selector: {selector}")
                                return True
                        except Exception as e:
                            self.logger.debug(f"Checkbox selector failed: {e}")
                            continue
                    return False
                return True  # If value is False, just skip (checkbox not checked)
            
            elif field.field_type == 'dropdown':
                # For dropdown/combobox fields
                element = await self.page.query_selector(field.css_selector)
                if element:
                    await self._fill_element(element, str(value))
                    await self._press_key(element, 'Enter')
                    return True
            
            else:
                # For text, email, phone, textarea fields - try multiple selectors
                selectors_to_try = [
                    f'input[name="{field.name}"]',
                    f'textarea[name="{field.name}"]',
                    f'input[id="{field.id}"]',
                    f'textarea[id="{field.id}"]',
                    field.css_selector
                ]
                
                for selector in selectors_to_try:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            await self._fill_element(element, str(value))
                            if VERBOSE:
                                self.logger.debug(f"Field filled with selector: {selector}")
                            return True
                    except Exception as e:
                        self.logger.debug(f"Field selector failed: {e}")
                        continue
                
                return False
            
        except Exception as e:
            self.logger.error(f"Error filling field: {e}")
            return False
    
    async def click_submit(self) -> bool:
        """
        Click the submit button to complete the contact info form.
        
        Returns:
            bool: True if submit button was clicked successfully, False otherwise
        """
        try:
            self.logger.info("Clicking submit button")
            
            # Use exact selector based on actual HTML structure
            button = await self.page.wait_for_selector(SUBMIT_BUTTON_SELECTOR, timeout=ELEMENT_TIMEOUT * 1.5)
            if button:
                self.logger.info(f"Found submit button with selector: {SUBMIT_BUTTON_SELECTOR}")
                
                # Scroll into view if needed
                await button.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(FIELD_INTERACTION_WAIT)
                
                # Click the button
                await button.click()
                self.logger.info("Submit button clicked successfully")
                
                # Wait for navigation/page update
                await self.page.wait_for_timeout(NEXT_BUTTON_WAIT)
                
                self.logger.info("Contact info form submitted")
                return True
            else:
                self.logger.error(f"Submit button not found with selector: {SUBMIT_BUTTON_SELECTOR}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error clicking submit button: {e}")
            return False
