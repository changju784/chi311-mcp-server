#!/usr/bin/env python3
"""
Configuration module for Chicago 311 automation.
Contains all timeout constants and configuration settings.
"""

# Timeout constants (in milliseconds)
ADDRESS_DROPDOWN_WAIT = 2000
FIELD_INTERACTION_WAIT = 100
CONFIRM_ADDRESS_WAIT = 1000
MULTISELECT_OPTION_WAIT = 100
NEXT_BUTTON_WAIT = 2000
CONTACT_PAGE_LOAD_WAIT = 3000
ELEMENT_TIMEOUT = 2000

# Verbose mode flag
VERBOSE = False

# Selector constants
ADDRESS_INPUT_SELECTOR = 'input.slds-input[placeholder*="address" i]'
ADDRESS_DROPDOWN_OPTION_SELECTOR = 'span[role="option"].slds-lookup__item-action'
APARTMENT_INPUT_SELECTOR = 'input[name="2ndAddress"]'
# Exact selector for confirm address button
CONFIRM_ADDRESS_BUTTON_SELECTOR = 'button.slds-button_brand.sfdc_button[data-aura-rendered-by]:has-text("Confirm Address")'
# Exact selectors based on actual HTML structure
NEXT_BUTTON_SELECTOR = 'button.slds-button.slds-button_brand.sfdc_button[data-aura-rendered-by]:has-text("next")'
# Exact selector for contact info page submit button
SUBMIT_BUTTON_SELECTOR = 'button.slds-button.slds-button_brand.sfdc_button[data-aura-rendered-by]:has-text("next")'

# Contact info field selectors
CONTACT_FIELD_SELECTORS = [
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
