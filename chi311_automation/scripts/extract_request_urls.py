#!/usr/bin/env python3
"""
Request URL Extractor for Chicago 311 Portal

Extracts CREATE REQUEST URLs for all Chicago 311 request types using parallel processing.
This script navigates through the Chicago 311 portal to find and extract the direct URLs
for creating service requests for each request type.
"""

import asyncio
import aiofiles
from playwright.async_api import async_playwright
import json
from datetime import datetime
import re
import os
import fcntl
import signal
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class RequestUrlExtractor:
    """
    Extracts CREATE REQUEST URLs for all Chicago 311 request types.
    
    This class handles parallel processing of request types to extract their
    direct URLs from the Chicago 311 portal. It includes proper error handling,
    progress tracking, and graceful shutdown on Ctrl+C.
    """
    
    def __init__(self, output_file: str = "311_urls_extraction.json", 
                 max_concurrent: int = 3):
        """
        Initialize the URL extractor.
        
        Args:
            output_file: Path to the output JSON file
            max_concurrent: Maximum number of concurrent browser instances
        """
        self.output_file = Path(output_file)
        self.max_concurrent = max_concurrent
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
    
    async def load_unified_data(self) -> Dict[str, Any]:
        """
        Load unified data from the request catalog.
        
        Returns:
            Dictionary containing request types data
        """
        try:
            async with aiofiles.open(self.output_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except FileNotFoundError:
            # Initialize with empty structure if file doesn't exist
            return {
                "metadata": {
                    "extraction_date": datetime.now().isoformat(),
                    "total_request_types": 0,
                    "extracted_urls": 0,
                    "failed_extractions": 0
                },
                "request_types": []
            }
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return {"request_types": []}
    
    async def save_unified_data(self, data: Dict[str, Any]) -> None:
        """
        Save unified data to file with atomic write.
        
        Args:
            data: Data dictionary to save
        """
        temp_file = self.output_file.with_suffix('.tmp')
        
        try:
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Atomic rename
            os.rename(temp_file, self.output_file)
        except Exception as e:
            print(f"❌ Error saving data: {e}")
            if temp_file.exists():
                temp_file.unlink()
    
    async def extract_url(self, request_type: Dict[str, Any], browser_id: int) -> Dict[str, Any]:
        """
        Extract URL for a single request type.
        
        Args:
            request_type: Dictionary containing request type information
            browser_id: ID of the browser instance for logging
            
        Returns:
            Dictionary with extraction results
        """
        request_name = request_type.get('name', 'Unknown')
        print(f"🌐 [Browser {browser_id}] Starting processing: {request_name}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            self.active_browsers.append(browser)
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                # Navigate to main portal
                print(f"🔍 [Browser {browser_id}] Navigating to main portal...")
                await page.goto("https://311.chicago.gov/s/service-request?language=en_US", 
                              wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                
                # Click View All button
                print(f"🔍 [Browser {browser_id}] Looking for View All button...")
                view_all_button = page.locator("text='View All'").first
                if await view_all_button.is_visible():
                    print(f"🔍 [Browser {browser_id}] Clicking View All button...")
                    await view_all_button.click()
                    await page.wait_for_timeout(3000)
                    await page.wait_for_load_state("networkidle")
                
                # Scroll to bottom of page
                print(f"🔍 [Browser {browser_id}] Scrolling page...")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                
                # Find CREATE REQUEST elements
                print(f"🔍 [Browser {browser_id}] Looking for CREATE REQUEST elements...")
                create_request_elements = await page.query_selector_all("*:has-text('CREATE REQUEST')")
                print(f"🔍 [Browser {browser_id}] Found {len(create_request_elements)} CREATE REQUEST elements...")
                
                # Look for the specific request type
                found = False
                extracted_url = None
                
                for element in create_request_elements:
                    try:
                        # Get parent container to find the request name
                        parent = await element.query_selector('xpath=..')
                        if parent:
                            parent_text = await parent.inner_text()
                            if request_name.lower() in parent_text.lower():
                                print(f"🔍 [Browser {browser_id}] Found matching request: {request_name}")
                                
                                # Click the CREATE REQUEST button
                                await element.click()
                                await page.wait_for_timeout(3000)
                                
                                # Get the current URL
                                current_url = page.url
                                if 'new-service-request' in current_url:
                                    extracted_url = current_url
                                    found = True
                                    print(f"✅ [Browser {browser_id}] Successfully extracted URL: {extracted_url}")
                                    break
                    except Exception as e:
                        print(f"⚠️ [Browser {browser_id}] Error processing element: {e}")
                        continue
                
                if not found:
                    print(f"❌ [Browser {browser_id}] Could not find or extract URL for: {request_name}")
                
                return {
                    'request_name': request_name,
                    'url': extracted_url,
                    'success': found,
                    'browser_id': browser_id,
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                print(f"❌ [Browser {browser_id}] Error processing {request_name}: {e}")
                return {
                    'request_name': request_name,
                    'url': None,
                    'success': False,
                    'error': str(e),
                    'browser_id': browser_id,
                    'timestamp': datetime.now().isoformat()
                }
            
            finally:
                await browser.close()
                if browser in self.active_browsers:
                    self.active_browsers.remove(browser)
    
    async def process_all_requests(self) -> None:
        """
        Process all request types in parallel.
        
        Loads request types from the catalog and processes them using
        the specified number of concurrent browser instances.
        """
        print("🚀 Starting Chicago 311 URL extraction...")
        
        # Load request catalog
        catalog_path = Path(__file__).parent.parent / 'data' / 'request_catalog.json'
        try:
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog_data = json.load(f)
                request_types = catalog_data["chicago_311_request_types"]["request_types"]
        except Exception as e:
            print(f"❌ Error loading request catalog: {e}")
            return
        
        print(f"📋 Found {len(request_types)} request types to process")
        
        # Load existing results
        existing_data = await self.load_unified_data()
        existing_urls = {item['request_name']: item for item in existing_data.get('request_types', [])}
        
        # Filter out already processed requests
        pending_requests = []
        for request_type in request_types:
            request_name = request_type.get('name', '')
            if request_name not in existing_urls:
                pending_requests.append(request_type)
        
        print(f"📝 {len(pending_requests)} requests pending extraction")
        
        if not pending_requests:
            print("✅ All requests already processed!")
            return
        
        # Process requests in parallel
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(request_type, browser_id):
            async with semaphore:
                return await self.extract_url(request_type, browser_id)
        
        # Create tasks
        tasks = []
        for i, request_type in enumerate(pending_requests):
            browser_id = (i % self.max_concurrent) + 1
            task = process_with_semaphore(request_type, browser_id)
            tasks.append(task)
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_extractions = 0
        failed_extractions = 0
        
        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Task failed with exception: {result}")
                failed_extractions += 1
                continue
            
            if result['success']:
                successful_extractions += 1
                existing_data['request_types'].append(result)
            else:
                failed_extractions += 1
        
        # Update metadata
        existing_data['metadata'] = {
            "extraction_date": datetime.now().isoformat(),
            "total_request_types": len(request_types),
            "extracted_urls": successful_extractions,
            "failed_extractions": failed_extractions
        }
        
        # Save results
        await self.save_unified_data(existing_data)
        
        print(f"\n📊 Extraction Summary:")
        print(f"  ✅ Successful: {successful_extractions}")
        print(f"  ❌ Failed: {failed_extractions}")
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
    """Main function to run the URL extraction process."""
    print_section_header("Chicago 311 Request URL Extractor")
    
    start_time = asyncio.get_event_loop().time()
    
    extractor = RequestUrlExtractor(
        output_file="311_urls_extraction.json",
        max_concurrent=3
    )
    
    try:
        await extractor.process_all_requests()
    except KeyboardInterrupt:
        print("\n🛑 Extraction interrupted by user")
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
    finally:
        elapsed_time = asyncio.get_event_loop().time() - start_time
        print(f"\n⏱️ Total elapsed time: {format_elapsed_time(elapsed_time)}")


if __name__ == "__main__":
    asyncio.run(main())
