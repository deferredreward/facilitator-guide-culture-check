#!/usr/bin/env python3
"""
Block Fetcher - Test individual Notion blocks

This script fetches a single Notion block and saves the full response for testing.
Usage: python test_block_fetcher.py <notion_block_url_or_id>
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

# Load environment variables
load_dotenv()

def extract_block_id_from_url(url_or_id):
    """
    Extract block ID from Notion URL or return as-is if already an ID
    
    Args:
        url_or_id (str): Notion block URL or block ID
        
    Returns:
        str: Clean block ID
    """
    if not url_or_id:
        return None
    
    # If it's already a clean ID (32 hex chars), return as-is
    if len(url_or_id) == 32 and all(c in '0123456789abcdef' for c in url_or_id.lower()):
        return url_or_id
    
    # Handle URLs with hash fragments (block links)
    if '#' in url_or_id:
        # Extract the part after the hash
        block_part = url_or_id.split('#')[-1]
        # Remove any hyphens to get clean ID
        clean_id = block_part.replace('-', '')
        if len(clean_id) == 32:
            return clean_id
    
    # Handle regular page URLs (extract from path)
    if 'notion.so' in url_or_id:
        # Extract the last part that looks like a page ID
        parts = url_or_id.split('/')
        for part in reversed(parts):
            if '-' in part:
                # Split on the last dash to get the ID part
                potential_id = part.split('-')[-1]
                if len(potential_id) == 32:
                    return potential_id
    
    # If all else fails, try to clean up what we have
    cleaned = url_or_id.replace('-', '').replace('?', '').split('#')[0].split('/')[-1]
    if len(cleaned) == 32:
        return cleaned
    
    return url_or_id

def fetch_block(block_id):
    """
    Fetch a block from Notion API
    
    Args:
        block_id (str): Notion block ID
        
    Returns:
        dict: Full API response
    """
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise ValueError("NOTION_API_KEY not found in environment variables")
    
    try:
        client = Client(auth=notion_token)
        print(f"Fetching block: {block_id}")
        
        # Fetch the block
        response = client.blocks.retrieve(block_id)
        print(f"Successfully fetched block of type: {response.get('type', 'unknown')}")
        
        return response
        
    except Exception as e:
        print(f"Error fetching block: {e}")
        raise

def save_block_response(block_id, response):
    """
    Save block response to a JSON file
    
    Args:
        block_id (str): Block ID
        response (dict): API response
        
    Returns:
        str: Path to saved file
    """
    # Create saved_blocks directory if it doesn't exist
    saved_blocks_dir = Path(__file__).parent / 'saved_blocks'
    saved_blocks_dir.mkdir(exist_ok=True)
    
    # Extract text content for filename
    text_content = ""
    if response.get('type') in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                               'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']:
        rich_text = response.get(response['type'], {}).get('rich_text', [])
        if rich_text:
            text_content = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
    
    # Clean text content for filename (remove invalid filename characters)
    clean_text = ""
    if text_content:
        # Remove/replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        clean_text = text_content[:15]
        for char in invalid_chars:
            clean_text = clean_text.replace(char, '_')
        # Remove emojis and other non-ASCII characters
        clean_text = ''.join(char for char in clean_text if ord(char) < 128)
        clean_text = clean_text.strip()
    
    # Create filename with text content and block ID
    if clean_text:
        filename = f"{clean_text}_{block_id[:8]}.json"
    else:
        filename = f"block_{block_id[:8]}.json"
    
    filepath = saved_blocks_dir / filename
    
    # Prepare data to save
    data = {
        'block_id': block_id,
        'fetched_at': datetime.now().isoformat(),
        'response': response
    }
    
    # Save to file with pretty formatting
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved block data to: {filepath}")
    return str(filepath)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Fetch and save a Notion block for testing',
        epilog='Example: python test_block_fetcher.py "https://www.notion.so/page#block-id"'
    )
    parser.add_argument(
        'block_url_or_id', 
        help='Notion block URL or block ID'
    )
    
    args = parser.parse_args()
    
    try:
        # Extract clean block ID
        block_id = extract_block_id_from_url(args.block_url_or_id)
        print(f"Input: {args.block_url_or_id}")
        print(f"Extracted Block ID: {block_id}")
        
        if not block_id or len(block_id) != 32:
            print(f"Invalid block ID: {block_id}")
            sys.exit(1)
        
        # Fetch the block
        response = fetch_block(block_id)
        
        # Save the response
        filepath = save_block_response(block_id, response)
        
        # Show summary
        print(f"\n{'='*60}")
        print(f"BLOCK FETCH COMPLETE")
        print(f"{'='*60}")
        print(f"Block ID: {block_id}")
        print(f"Block Type: {response.get('type', 'unknown')}")
        print(f"Saved to: {filepath}")
        
        # Show text content if available
        if response.get('type') in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                                   'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']:
            rich_text = response.get(response['type'], {}).get('rich_text', [])
            if rich_text:
                text_content = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
                print(f"Text Content: {text_content[:100]}{'...' if len(text_content) > 100 else ''}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()