#!/usr/bin/env python3
"""
Form handler module for Chicago 311 forms.
This module provides form field filling functionality using JSON field data.
"""

import logging
from playwright.async_api import Page
from typing import Dict, Any, List, Union, Optional
from .base_handler import BaseHandler
from .config import (
    FIELD_INTERACTION_WAIT,
    MULTISELECT_OPTION_WAIT,
    NEXT_BUTTON_WAIT,
    ELEMENT_TIMEOUT,
    NEXT_BUTTON_SELECTOR,
    VERBOSE
)


class FormHandler(BaseHandler):
    """
    Handler for Chicago 311 form field filling.
    
    Provides methods to fill various types of form fields including text,
    dropdown, multiselect, date, time, and number fields based on JSON metadata.
    
    Example:
        form_handler = FormHandler(page)
        results = await form_handler.fill_form(fields, data)
        await form_handler.click_next()
    """
    
    def __init__(self, page: Page):
        """
        Initialize the form handler.
        
        Args:
            page: Playwright page object
        """
        super().__init__(page)
    
    async def fill_field(self, field: Dict[str, Any], value: Any) -> bool:
        """
        Fill a single form field based on field metadata and value.
        
        Args:
            field: Field metadata dictionary containing type, selectors, etc.
            value: Value to fill in the field
            
        Returns:
            bool: True if field was filled successfully, False otherwise
        """
        field_type = field.get('field_type')
        field_id = field.get('id', '')
        field_name = field.get('name', '')
        label = field.get('label', '')
        
        self.logger.info(f"Processing field: {label}")
        if VERBOSE:
            self.logger.debug(f"Field type: {field_type}, ID: {field_id}, Name: {field_name}")
            self.logger.debug(f"Trying to fill with: '{value}'")
        
        # Build selector list
        selectors_to_try = []
        
        # For dropdowns, prioritize datalist_id selector (most reliable)
        if field_type == 'dropdown' and field.get('datalist_id'):
            datalist_selector = f'input[list="{field["datalist_id"]}"]'
            selectors_to_try.append(datalist_selector)
            if VERBOSE:
                self.logger.debug(f"Using datalist selector: {datalist_selector}")
        
        # Use CSS selector from JSON
        if field.get('css_selector'):
            selectors_to_try.append(field['css_selector'])
        
        # Use XPath selector from JSON
        if field.get('xpath'):
            selectors_to_try.append(field['xpath'])
        
        # Add name-based selectors
        if field_name:
            selectors_to_try.append(f'input[name="{field_name}"]')
            selectors_to_try.append(f'textarea[name="{field_name}"]')
            selectors_to_try.append(f'select[name="{field_name}"]')
        
        # Try each selector
        for i, selector in enumerate(selectors_to_try, 1):
            try:
                if VERBOSE:
                    self.logger.debug(f"Selector {i}/{len(selectors_to_try)}: {selector}")
                element = await self.page.wait_for_selector(selector, timeout=ELEMENT_TIMEOUT)
                if element:
                    if VERBOSE:
                        self.logger.debug(f"Found element with selector: {selector}")
                        self.logger.debug("Proceeding with field interaction...")
                    
                    # Handle different field types
                    success = await self._interact_with_field(element, field, value)
                    if success:
                        return True
                        
            except Exception as e:
                self.logger.debug(f"Selector failed: {e}")
                continue
        
        return False
    
    async def _interact_with_field(self, element, field: Dict[str, Any], value: Any) -> bool:
        """
        Interact with a field based on its type and metadata.
        
        Args:
            element: Playwright element
            field: Field metadata dictionary
            value: Value to fill
            
        Returns:
            bool: True if interaction was successful, False otherwise
        """
        field_type = field.get('field_type')
        interaction_method = field.get('interaction_method', 'fill')
        
        try:
            if field_type == 'dropdown':
                if VERBOSE:
                    self.logger.debug(f"Dropdown interaction method: {interaction_method}")
                
                if interaction_method == 'select':
                    if VERBOSE:
                        self.logger.debug(f"Step 1: Filling dropdown with text: '{value}'")
                    await self._fill_element(element, str(value))
                    
                    if VERBOSE:
                        self.logger.debug("Step 2: Pressing Enter key")
                    await self._press_key(element, 'Enter')
                    
                    self.logger.info("Dropdown selection completed")
                    return True
                else:
                    # For regular select elements
                    if field.get('options'):
                        option_text = value
                        option_selector = f'option:has-text("{option_text}")'
                        try:
                            option = await self.page.wait_for_selector(option_selector, timeout=ELEMENT_TIMEOUT / 2)
                            if option:
                                await option.click()
                                self.logger.info("Select option clicked")
                                return True
                        except Exception as e:
                            self.logger.debug(f"Failed to select option '{option_text}': {e}")
                            
            elif field_type == 'multiselect':
                return await self._handle_multiselect(field, value)
                
            elif field_type in ['text', 'textarea', 'date']:
                if VERBOSE:
                    self.logger.debug(f"Filling {field_type} field with: '{value}'")
                await self._fill_element(element, str(value))
                self.logger.info(f"{field_type} field filled successfully")
                return True
                
            elif field_type == 'time':
                if VERBOSE:
                    self.logger.debug("Time field detected")
                    self.logger.debug(f"Filling time field with: '{value}'")
                await self._fill_element(element, str(value))
                self.logger.info("Time field filled successfully")
                return True
                
            elif field_type == 'number':
                if VERBOSE:
                    self.logger.debug("Number field detected")
                    self.logger.debug(f"Filling number field with: '{value}'")
                await self._fill_element(element, str(value))
                self.logger.info("Number field filled successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Field interaction failed: {e}")
            return False
        
        return False
    
    async def _handle_multiselect(self, field: Dict[str, Any], value: Any) -> bool:
        """
        Handle multiselect field interaction.
        
        Args:
            field: Field metadata
            value: Values to select (list or single value)
            
        Returns:
            bool: True if multiselect was handled successfully
        """
        self.logger.info("Multiselect field detected")
        values_to_select = value if isinstance(value, list) else [value]
        if VERBOSE:
            self.logger.debug(f"Values to select: {values_to_select}")
        
        # Get the specific multiselect container ID
        field_id = field.get('id', '')
        if not field_id:
            self.logger.error("No field ID found for multiselect")
            return False
        
        if VERBOSE:
            self.logger.debug(f"Targeting multiselect container: {field_id}")
        
        successfully_selected_count = 0
        for option_value in values_to_select:
            if VERBOSE:
                self.logger.debug(f"Selecting option: {option_value}")
            
            try:
                # 1. Find the specific multiselect container
                container_selector = f'ul#{field_id}'
                container = await self.page.query_selector(container_selector)
                
                if not container:
                    self.logger.error(f"Multiselect container '{field_id}' not found")
                    continue
                
                # 2. Find and click option in Available list within this container
                option_selectors = [
                    f'ul#{field_id} div[role="option"]:has-text("{option_value}")',
                    f'ul#{field_id} li:has-text("{option_value}")',
                    f'ul#{field_id} [data-value="{option_value}"]',
                    f'ul#{field_id} div:has-text("{option_value}")'
                ]
                
                option = None
                for option_selector in option_selectors:
                    try:
                        option = await self.page.query_selector(option_selector)
                        if option:
                            if VERBOSE:
                                self.logger.debug(f"Found option with selector: {option_selector}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Option selector failed: {e}")
                        continue
                
                if option:
                    # Scroll into view if needed
                    await option.scroll_into_view_if_needed()
                    await self.page.wait_for_timeout(MULTISELECT_OPTION_WAIT)
                    
                    # Click option
                    await option.click()
                    await self.page.wait_for_timeout(MULTISELECT_OPTION_WAIT)
                    if VERBOSE:
                        self.logger.debug(f"Option '{option_value}' clicked")
                    
                    # 3. Find and click the "Move to Selected" button for this specific multiselect
                    group_label_id = f"group-label-{field_id.split('-')[-1]}"
                    move_button = await self.page.query_selector(f'[aria-labelledby="{group_label_id}"] button[title="Move to Selected"]')
                    
                    if move_button:
                        await move_button.click()
                        await self.page.wait_for_timeout(MULTISELECT_OPTION_WAIT)
                        if VERBOSE:
                            self.logger.debug(f"Moved '{option_value}' to Selected using group-specific button (group: {group_label_id})")
                        successfully_selected_count += 1
                    else:
                        self.logger.error(f"Move button not found for group '{group_label_id}'")
                else:
                    self.logger.error(f"Option '{option_value}' not found in multiselect '{field_id}'")
                    
            except Exception as e:
                self.logger.error(f"Error selecting '{option_value}': {e}")
        
        if successfully_selected_count > 0:
            self.logger.info(f"Successfully selected {successfully_selected_count}/{len(values_to_select)} options")
            return True
        else:
            self.logger.error("No options were selected")
            return False
    
    async def fill_form(self, fields: List[Dict[str, Any]], data: Dict[str, Any]) -> Dict[str, int]:
        """
        Fill an entire form with provided data.
        
        Args:
            fields: List of field metadata dictionaries
            data: Dictionary mapping field labels to values
            
        Returns:
            Dict with counts of filled, failed, and skipped fields
        """
        filled_count = 0
        failed_count = 0
        skipped_count = 0
        
        self.logger.info("Starting form filling")
        
        for field in fields:
            label = field.get('label', '')
            field_type = field.get('field_type', '')
            
            if VERBOSE:
                self.logger.debug(f"Field: {label}")
                self.logger.debug(f"Type: {field_type}, ID: {field.get('id', '')}, Name: {field.get('name', '')}")
            
            if label in data:
                value = data[label]
                success = await self.fill_field(field, value)
                
                if success:
                    filled_count += 1
                else:
                    failed_count += 1
            else:
                if VERBOSE:
                    self.logger.debug("No sample data for this field")
                skipped_count += 1
        
        self.logger.info("Form filling results:")
        self.logger.info(f"Successfully filled: {filled_count}/{len(fields)}")
        self.logger.info(f"Failed to fill: {failed_count}/{len(fields)}")
        self.logger.info(f"Skipped (no data): {skipped_count}/{len(fields)}")
        
        if failed_count == 0 and filled_count > 0:
            self.logger.info("Current JSON data is sufficient for form filling")
        elif failed_count > 0:
            self.logger.warning("Some fields failed to fill")
        
        return {
            'filled': filled_count,
            'failed': failed_count,
            'skipped': skipped_count,
        }
    
    async def click_next(self) -> bool:
        """
        Click the Next button to proceed to the next page.
        
        Returns:
            bool: True if Next button was clicked successfully, False otherwise
        """
        try:
            self.logger.info("Clicking Next button")
            
            # Use exact selector based on actual HTML structure
            button = await self.page.wait_for_selector(NEXT_BUTTON_SELECTOR, timeout=ELEMENT_TIMEOUT * 1.5)
            if button:
                self.logger.info(f"Found Next button with selector: {NEXT_BUTTON_SELECTOR}")
                
                # Scroll into view if needed
                await button.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(FIELD_INTERACTION_WAIT)
                
                # Click the button
                await button.click()
                self.logger.info("Next button clicked successfully")
                
                # Wait for navigation/page update
                await self.page.wait_for_timeout(NEXT_BUTTON_WAIT)
                
                self.logger.info("Proceeding to next page...")
                return True
            else:
                self.logger.error(f"Next button not found with selector: {NEXT_BUTTON_SELECTOR}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error clicking Next button: {e}")
            return False
