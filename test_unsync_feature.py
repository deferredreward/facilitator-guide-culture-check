#!/usr/bin/env python3
"""
Test script for the new unsync blocks feature

This script tests the synced block identification and unsyncing functionality
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from notion_writer import NotionWriter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def test_find_synced_blocks(page_id):
    """Test finding synced blocks on a page"""
    logging.info(f"🔍 Testing synced block detection on page {page_id}")
    
    try:
        writer = NotionWriter()
        synced_blocks = writer.find_synced_blocks(page_id)
        
        if not synced_blocks:
            logging.info("✅ No synced blocks found on page")
            return True
        
        logging.info(f"🔗 Found {len(synced_blocks)} synced blocks:")
        for i, block in enumerate(synced_blocks, 1):
            block_type = "original" if block['is_original'] else "reference"
            synced_from = f" -> {block['synced_from_id'][:8]}..." if block['synced_from_id'] else ""
            logging.info(f"   {i}. {block['id'][:8]}... ({block_type}){synced_from}")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error testing synced block detection: {e}")
        return False

def test_unsync_dry_run(page_id):
    """Test unsync in dry-run mode"""
    logging.info(f"🌀 Testing unsync dry-run on page {page_id}")
    
    try:
        writer = NotionWriter()
        result = writer.unsync_blocks_on_page(page_id, dry_run=True)
        
        if result['success']:
            if result.get('dry_run'):
                logging.info(f"✅ Dry-run completed - would unsync {result.get('blocks_found', 0)} blocks")
            else:
                logging.info(f"✅ {result['message']}")
            return True
        else:
            logging.error(f"❌ Dry-run failed: {result.get('error', 'Unknown error')}")
            return False
        
    except Exception as e:
        logging.error(f"❌ Error testing dry-run: {e}")
        return False

def get_page_id():
    """Get page ID from command line arguments or prompt user"""
    parser = argparse.ArgumentParser(description='Test unsync blocks feature')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to test unsync feature:")
        page_id = input().strip()
        
        if not page_id:
            logging.error("❌ No page ID provided")
            sys.exit(1)
    
    return page_id

def main():
    """Main function to run the tests"""
    logging.info("🚀 Starting Unsync Feature Test...")
    
    # Get page ID
    page_id = get_page_id()
    
    # Test 1: Find synced blocks
    test1_passed = test_find_synced_blocks(page_id)
    
    if not test1_passed:
        logging.error("❌ Test 1 failed - cannot proceed")
        sys.exit(1)
    
    # Test 2: Dry-run unsync
    test2_passed = test_unsync_dry_run(page_id)
    
    if test2_passed:
        logging.info("🎉 All tests passed successfully!")
        logging.info("💡 To actually unsync blocks, use: python orchestrator.py <page_id> --unsync-blocks")
    else:
        logging.error("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()