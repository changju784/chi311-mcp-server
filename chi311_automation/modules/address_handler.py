#!/usr/bin/env python3
"""
Address handler module for Chicago 311 forms.
This module provides address input and confirmation functionality.
"""

import logging
from playwright.async_api import Page
from typing import Optional
from .base_handler import BaseHandler
from .config import (
    ADDRESS_DROPDOWN_WAIT,
    FIELD_INTERACTION_WAIT,
    CONFIRM_ADDRESS_WAIT,
    ELEMENT_TIMEOUT,
    ADDRESS_INPUT_SELECTOR,
    ADDRESS_DROPDOWN_OPTION_SELECTOR,
    APARTMENT_INPUT_SELECTOR,
    CONFIRM_ADDRESS_BUTTON_SELECTOR,
    VERBOSE
)


class AddressHandler(BaseHandler):
    """
    Handler for Chicago 311 address input and confirmation.
    
    Provides methods to set up address information on Chicago 311 forms,
    including address input, dropdown selection, apartment number entry,
    and address confirmation.
    
    Example:
        address_handler = AddressHandler(page)
        success = await address_handler.setup("123 Main St, Chicago, IL", "Apt 1B")
        if success:
            await address_handler.verify_setup()
    """
    
    def __init__(self, page: Page):
        """
        Initialize the address handler.
        
        Args:
            page: Playwright page object
        """
        super().__init__(page)
    
    async def setup(self, address: str, apt: str = "") -> bool:
        """
        Setup address on the Chicago 311 form.

        Args:
            address: Address to enter (required)
            apt: Apartment/suite number (optional, defaults to empty string)
        
        Returns:
            bool: True if address setup was successful, False otherwise
            
        Raises:
            TimeoutError: If address input field is not found
            Exception: If address setup fails at any step
        """
        try:
            self.logger.info("Setting up address...")
            if VERBOSE:
                self.logger.debug(f"Address: {address}, Apt: {apt}")
            
            # Enter address
            try:
                address_input = await self._wait_for_element(ADDRESS_INPUT_SELECTOR, ELEMENT_TIMEOUT * 5)
                if not address_input:
                    raise TimeoutError("Address input field not found")
                
                await self._fill_element(address_input, address)
                await self.page.wait_for_timeout(ADDRESS_DROPDOWN_WAIT)
                self.logger.debug("Address entered successfully")
            except Exception as e:
                self.logger.error(f"Failed to enter address: {e}")
                raise TimeoutError("Address input field not found")
            
            # Select from dropdown
            try:
                dropdown_option = await self._wait_for_element(ADDRESS_DROPDOWN_OPTION_SELECTOR, ELEMENT_TIMEOUT * 2.5)
                if not dropdown_option:
                    raise Exception("Address dropdown selection failed")
                
                await self._click_element(dropdown_option)
                self.logger.debug("Address dropdown option selected")
            except Exception as e:
                self.logger.error(f"Failed to select address from dropdown: {e}")
                raise Exception("Address dropdown selection failed")
            
            # Enter apartment/suite if field exists
            try:
                apt_input = await self._wait_for_element(APARTMENT_INPUT_SELECTOR, ELEMENT_TIMEOUT * 1.5)
                if apt_input:
                    await self._fill_element(apt_input, apt)
                    self.logger.debug(f"Apartment number entered: {apt}")
            except Exception as e:
                self.logger.debug(f"Apartment field not found or failed to fill: {e}")
            
            # Confirm address
            try:
                confirm_button = await self._wait_for_element(CONFIRM_ADDRESS_BUTTON_SELECTOR, ELEMENT_TIMEOUT * 2.5)
                if not confirm_button:
                    raise Exception("Address confirmation failed")
                
                await self._click_element(confirm_button, CONFIRM_ADDRESS_WAIT)
                self._log_operation("Address setup", True)
                return True
            except Exception as e:
                self.logger.error(f"Failed to confirm address: {e}")
                raise Exception("Address confirmation failed")
            
        except Exception as e:
            self._log_operation("Address setup", False, str(e))
            return False
    
    async def setup_with_retry(self, address: str, apt: str = "", max_retries: int = 3) -> bool:
        """
        Setup address with retry mechanism.
        
        Args:
            address: Address to enter
            apt: Apartment/suite number
            max_retries: Maximum number of retry attempts
        
        Returns:
            bool: True if address setup was successful, False otherwise
        """
        for attempt in range(max_retries):
            self.logger.info(f"Address setup attempt {attempt + 1}/{max_retries}")
            
            success = await self.setup(address, apt)
            if success:
                return True
                
            if attempt < max_retries - 1:
                self.logger.warning("Retrying address setup...")
                await self.page.wait_for_timeout(FIELD_INTERACTION_WAIT * 5)
        
        self._log_operation("Address setup", False, f"failed after {max_retries} attempts")
        return False
    
    async def verify_setup(self) -> bool:
        """
        Verify that address setup was successful by checking for form fields.
        
        Args:
            page: Playwright page object
        
        Returns:
            bool: True if form fields are visible (address setup successful), False otherwise
        """
        try:
            # Look for form fields that appear after address setup
            form_indicators = [
                'input.search-list-input',
                'lightning-textarea',
                'lightning-datepicker',
                '.slds-col.slds-p-vertical_x-small'
            ]
            
            for indicator in form_indicators:
                element = await self._wait_for_element(indicator, ELEMENT_TIMEOUT)
                if element:
                    self._log_operation("Address setup verification", True, "form fields detected")
                    return True
                else:
                    self.logger.debug(f"Form indicator '{indicator}' not found")
            
            self._log_operation("Address setup verification", False, "no form fields detected")
            return False
            
        except Exception as e:
            self._log_operation("Address setup verification", False, str(e))
            return False
