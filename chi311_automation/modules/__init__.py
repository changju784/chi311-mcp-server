"""
Chicago 311 Automation Modules

This package contains reusable modules for automating Chicago 311 form submissions.

Usage:
    from chi311_automation.modules import configure_logging, AddressHandler, FormHandler, ContactHandler
    
    # Configure logging for verbose output
    configure_logging(verbose=True)
    
    # Use the handlers
    address_handler = AddressHandler(page)
    await address_handler.setup("123 Main St", "Apt 1B")
    
    form_handler = FormHandler(page)
    await form_handler.fill_form(fields, data)
    await form_handler.click_next()
    
    contact_handler = ContactHandler(page)
    await contact_handler.fill_contact_info(contact_data)
"""

import logging
from .config import *
from .base_handler import BaseHandler
from .address_handler import AddressHandler
from .form_handler import FormHandler
from .contact_handler import ContactHandler, ContactField

__all__ = [
    'configure_logging',
    'BaseHandler',
    'AddressHandler',
    'FormHandler',
    'ContactHandler',
    'ContactField'
]

def configure_logging(verbose: bool = False, level: int = logging.INFO):
    """
    Configure module-wide logging.
    
    Args:
        verbose: If True, enables debug-level logging for detailed output
        level: Logging level (default: logging.INFO)
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Override any existing configuration
    )
    
    # Set verbose mode in config
    import chi311_automation.modules.config as config
    config.VERBOSE = verbose

