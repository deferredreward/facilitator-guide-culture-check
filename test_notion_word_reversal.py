#!/usr/bin/env python3
"""
Test script for Notion word reversal functionality

This script tests the ability to find blocks starting with ❓ emoji
and reverse all words in them non-destructively.
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from notion_writer import NotionWriter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def get_page_id():
    """Get page ID from command line arguments or prompt user"""
    parser = argparse.ArgumentParser(description='Test word reversal on Notion blocks')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    parser.add_argument('--emoji', default='❓', help='Emoji to search for (default: ❓)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--refresh-cache', action='store_true', help='Refresh the page cache before testing')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to test word reversal:")
        page_id = input().strip()
        
        if not page_id:
            logging.error("❌ No page ID provided")
            sys.exit(1)
    
    return page_id, args.emoji, args.dry_run, args.refresh_cache

def test_word_reversal_logic():
    """Test the word reversal logic with sample text"""
    logging.info("🧪 Testing word reversal logic...")
    
    writer = NotionWriter()
    
    test_cases = [
        "❓ What is the purpose of this test?",
        "❓ How does this work with punctuation!",
        "❓ Testing with numbers: 123 and symbols @#$",
        "❓ Multiple words will be reversed individually",
        "❓ Single",
        "❓ This-is-hyphenated and this_is_underscored"
    ]
    
    for original in test_cases:
        reversed_text = writer.reverse_words_in_text(original)
        logging.info(f"Original: {original}")
        logging.info(f"Reversed: {reversed_text}")
        logging.info("-" * 50)
    
    return True

def refresh_page_cache(page_id):
    """Refresh the page cache by running the notion scraper"""
    try:
        logging.info(f"🔄 Refreshing cache for page {page_id}...")
        
        # Run the notion scraper to refresh the cache
        result = subprocess.run(
            [sys.executable, "notion_scraper.py", page_id],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            logging.info("✅ Cache refreshed successfully!")
            return True
        else:
            logging.error(f"❌ Failed to refresh cache: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error refreshing cache: {e}")
        return False

def check_and_refresh_cache(page_id, force_refresh=False):
    """Check if cache needs refreshing and prompt user if needed"""
    from pathlib import Path
    saved_pages_dir = Path("saved_pages")
    debug_file = saved_pages_dir / f"notion_page_{page_id}_debug.json"
    
    # If cache doesn't exist, we must refresh
    if not debug_file.exists():
        logging.info(f"📂 No cached data found for page {page_id}")
        logging.info("🔄 Cache refresh is required...")
        return refresh_page_cache(page_id)
    
    # If force refresh is requested, do it
    if force_refresh:
        return refresh_page_cache(page_id)
    
    # Otherwise, prompt user
    print(f"\n🗂️ Found cached data for page {page_id}")
    print("❓ Do you want to refresh the cache to get the latest data? (y/N): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        return refresh_page_cache(page_id)
    else:
        logging.info("📋 Using existing cached data")
        return True

def test_notion_page_reversal(page_id, emoji="❓", dry_run=False):
    """Test the full Notion page word reversal functionality"""
    logging.info(f"🔍 Testing word reversal on page {page_id}")
    logging.info(f"🎯 Looking for blocks starting with: {emoji}")
    
    if dry_run:
        logging.info("🌀 DRY RUN MODE - No actual changes will be made")
    
    try:
        # Initialize writer
        writer = NotionWriter()
        
        # First, just find the blocks to see what we're working with
        logging.info("📋 Finding blocks that start with the emoji...")
        matching_blocks = writer.find_blocks_starting_with_emoji(page_id, emoji)
        
        if not matching_blocks:
            logging.warning(f"⚠️ No blocks found starting with '{emoji}'")
            return False
        
        logging.info(f"✅ Found {len(matching_blocks)} blocks starting with '{emoji}'")
        
        # Show what would be changed
        for i, block in enumerate(matching_blocks, 1):
            original_text = writer._extract_plain_text_from_block(block)
            reversed_text = writer.reverse_words_in_text(original_text)
            
            logging.info(f"\n📝 Block {i} (ID: {block['id']}):")
            logging.info(f"   Type: {block.get('type')}")
            logging.info(f"   Original: {original_text}")
            logging.info(f"   Reversed: {reversed_text}")
        
        if dry_run:
            logging.info("\n🌀 DRY RUN MODE - Stopping here. No changes made.")
            return True
        
        # Ask for confirmation
        print(f"\n❓ Do you want to proceed with updating {len(matching_blocks)} blocks? (y/N): ", end="")
        response = input().strip().lower()
        
        if response != 'y':
            logging.info("❌ Operation cancelled by user")
            return False
        
        # Perform the actual reversal
        logging.info("🔄 Performing word reversal...")
        result = writer.process_question_block_reversal(page_id, emoji)
        
        if result['success']:
            logging.info(f"✅ {result['message']}")
            logging.info(f"📊 Blocks processed: {result['blocks_processed']}")
            logging.info(f"📊 Successful updates: {result['successful_updates']}")
            
            # Show detailed results
            for i, block_result in enumerate(result['results'], 1):
                if block_result['success']:
                    logging.info(f"\n✅ Block {i} updated successfully:")
                    logging.info(f"   ID: {block_result['block_id']}")
                    logging.info(f"   Original: {block_result['original_text']}")
                    logging.info(f"   Reversed: {block_result['reversed_text']}")
                else:
                    logging.error(f"\n❌ Block {i} failed to update:")
                    logging.error(f"   ID: {block_result['block_id']}")
                    logging.error(f"   Error: {block_result['error']}")
            
            return True
        else:
            logging.error(f"❌ {result['message']}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error during testing: {e}")
        return False

def main():
    """Main function to run the test"""
    logging.info("🚀 Starting Notion Word Reversal Test...")
    
    # Get parameters
    page_id, emoji, dry_run, refresh_cache = get_page_id()
    
    # Check and refresh cache if needed
    cache_ready = check_and_refresh_cache(page_id, force_refresh=refresh_cache)
    
    if not cache_ready:
        logging.error("❌ Failed to prepare cache")
        sys.exit(1)
    
    # Test the word reversal logic first
    logic_test_passed = test_word_reversal_logic()
    
    if not logic_test_passed:
        logging.error("❌ Word reversal logic test failed")
        sys.exit(1)
    
    # Test on the actual Notion page
    page_test_passed = test_notion_page_reversal(page_id, emoji, dry_run)
    
    if page_test_passed:
        logging.info("🎉 All tests passed successfully!")
    else:
        logging.error("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 