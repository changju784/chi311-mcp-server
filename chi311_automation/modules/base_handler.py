#!/usr/bin/env python3
"""
Base handler class for Chicago 311 automation modules.
Provides common functionality for all automation handlers.
"""

import logging
from abc import ABC
from playwright.async_api import Page
from typing import List, Optional, Any
from .config import (
    FIELD_INTERACTION_WAIT,
    ELEMENT_TIMEOUT,
    VERBOSE
)


class BaseHandler(ABC):
    """
    Base class for all Chi311 automation handlers.
    
    Provides common functionality for element interaction, logging, and error handling.
    All handlers should inherit from this class for consistency.
    """
    
    def __init__(self, page: Page):
        """
        Initialize the base handler.
        
        Args:
            page: Playwright page object
        """
        self.page = page
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def _wait_for_element(self, selector: str, timeout: int = ELEMENT_TIMEOUT) -> Optional[Any]:
        """
        Wait for an element to appear on the page.
        
        Args:
            selector: CSS selector for the element
            timeout: Maximum time to wait in milliseconds
            
        Returns:
            Element if found, None if timeout
        """
        try:
            if VERBOSE:
                self.logger.debug(f"Waiting for element: {selector}")
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                if VERBOSE:
                    self.logger.debug(f"Element found: {selector}")
                return element
            return None
        except Exception as e:
            self.logger.debug(f"Element not found: {selector} - {e}")
            return None
    
    async def _click_element(self, element, wait_time: int = FIELD_INTERACTION_WAIT) -> bool:
        """
        Click an element with scroll into view and wait.
        
        Args:
            element: Playwright element to click
            wait_time: Time to wait after clicking
            
        Returns:
            True if click was successful, False otherwise
        """
        try:
            await element.scroll_into_view_if_needed()
            await self.page.wait_for_timeout(wait_time)
            await element.click()
            await self.page.wait_for_timeout(wait_time)
            if VERBOSE:
                self.logger.debug("Element clicked successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to click element: {e}")
            return False
    
    async def _fill_element(self, element, value: str, wait_time: int = FIELD_INTERACTION_WAIT) -> bool:
        """
        Fill an element with text and wait.
        
        Args:
            element: Playwright element to fill
            value: Text value to fill
            wait_time: Time to wait after filling
            
        Returns:
            True if fill was successful, False otherwise
        """
        try:
            await element.fill(value)
            await self.page.wait_for_timeout(wait_time)
            if VERBOSE:
                self.logger.debug(f"Element filled with: {value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to fill element: {e}")
            return False
    
    async def _try_selectors(self, selectors: List[str], timeout: int = ELEMENT_TIMEOUT) -> Optional[Any]:
        """
        Try multiple selectors until one succeeds.
        
        Args:
            selectors: List of CSS selectors to try
            timeout: Timeout for each selector
            
        Returns:
            First element found, or None if all fail
        """
        for i, selector in enumerate(selectors, 1):
            try:
                if VERBOSE:
                    self.logger.debug(f"Trying selector {i}/{len(selectors)}: {selector}")
                element = await self.page.wait_for_selector(selector, timeout=timeout)
                if element:
                    if VERBOSE:
                        self.logger.debug(f"Found element with selector: {selector}")
                    return element
            except Exception as e:
                self.logger.debug(f"Selector failed: {e}")
                continue
        
        self.logger.warning(f"No element found with any of {len(selectors)} selectors")
        return None
    
    async def _press_key(self, element, key: str, wait_time: int = FIELD_INTERACTION_WAIT) -> bool:
        """
        Press a key on an element and wait.
        
        Args:
            element: Playwright element
            key: Key to press (e.g., 'Enter', 'Tab')
            wait_time: Time to wait after pressing
            
        Returns:
            True if key press was successful, False otherwise
        """
        try:
            await element.press(key)
            await self.page.wait_for_timeout(wait_time)
            if VERBOSE:
                self.logger.debug(f"Key '{key}' pressed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to press key '{key}': {e}")
            return False
    
    def _log_operation(self, operation: str, success: bool, details: str = ""):
        """
        Log operation results consistently.
        
        Args:
            operation: Name of the operation
            success: Whether the operation succeeded
            details: Additional details to log
        """
        if success:
            self.logger.info(f"{operation} completed successfully{f': {details}' if details else ''}")
        else:
            self.logger.error(f"{operation} failed{f': {details}' if details else ''}")
    
    async def _wait_for_navigation(self, wait_time: int = 2000) -> None:
        """
        Wait for page navigation to complete.
        
        Args:
            wait_time: Time to wait in milliseconds
        """
        try:
            await self.page.wait_for_load_state('domcontentloaded')
            await self.page.wait_for_timeout(wait_time)
            if VERBOSE:
                self.logger.debug("Navigation completed")
        except Exception as e:
            self.logger.debug(f"Navigation wait completed with warning: {e}")
