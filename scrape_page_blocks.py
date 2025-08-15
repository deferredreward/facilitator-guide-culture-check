#!/usr/bin/env python3
"""
Page Block Scraper - Extract first N blocks from a Notion page as JSON

This script fetches the first N blocks from a Notion page and saves them as JSON.
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

CONTAINER_TYPES = {
    'paragraph', 'heading_1', 'heading_2', 'heading_3',
    'bulleted_list_item', 'numbered_list_item', 'to_do', 'toggle',
    'quote', 'callout', 'column_list', 'column', 'table', 'table_row'
}

def _has_children_probe(client, block_id):
    """Lightweight probe to verify if a block actually has children.

    Uses page_size=1 to minimize API calls. Returns True if at least one child exists.
    """
    try:
        resp = client.blocks.children.list(block_id=block_id, page_size=1)
        return len(resp.get('results', [])) > 0
    except Exception:
        return False

def get_block_children_recursively(client, block_id, depth=0, max_depth=5):
    """
    Recursively get all children of a block
    
    Args:
        client: Notion client
        block_id (str): Block ID to get children for
        depth (int): Current recursion depth
        max_depth (int): Maximum recursion depth
        
    Returns:
        list: All child blocks with their children
    """
    if depth >= max_depth:
        return []
    
    all_children = []
    start_cursor = None
    
    try:
        while True:
            response = client.blocks.children.list(
                block_id=block_id,
                page_size=100,
                start_cursor=start_cursor
            )
            
            children = response.get('results', [])
            
            for child in children:
                # Add this child to our list
                all_children.append(child)

                # Decide if we should recurse into this child
                child_id = child.get('id')
                block_type = child.get('type')
                has_children_flag = child.get('has_children', False)

                should_check_children = has_children_flag
                # If API reports false but type commonly nests children, do a cheap probe
                if not should_check_children and block_type in CONTAINER_TYPES and child_id:
                    if _has_children_probe(client, child_id):
                        should_check_children = True

                if should_check_children and child_id:
                    grandchildren = get_block_children_recursively(
                        client, child_id, depth + 1, max_depth
                    )
                    all_children.extend(grandchildren)
            
            if not response.get('has_more', False):
                break
                
            start_cursor = response.get('next_cursor')
            
    except Exception as e:
        print(f"  Error getting children for block {block_id}: {e}")
    
    return all_children

def scrape_page_blocks(page_id, limit=None, include_children=True):
    """
    Scrape blocks from a Notion page
    
    Args:
        page_id (str): Notion page ID
        limit (int): Number of blocks to fetch (None for all blocks)
        include_children (bool): Whether to recursively get child blocks
        
    Returns:
        dict: Page info and blocks data
    """
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise ValueError("NOTION_API_KEY not found in environment variables")
    
    client = Client(auth=notion_token)
    
    print(f"Scraping page: {page_id}")
    if limit:
        print(f"Fetching first {limit} blocks...")
    else:
        print(f"Fetching ALL blocks...")
    
    try:
        # Get page info
        page_info = client.pages.retrieve(page_id)
        print(f"Page title: {page_info.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled')}")
        
        # Get all blocks by paginating through results
        all_blocks = []
        start_cursor = None
        page_count = 0
        
        while True:
            page_count += 1
            print(f"  Fetching page {page_count}...")
            
            if limit and len(all_blocks) >= limit:
                # If we have enough blocks, break
                break
                
            remaining_limit = limit - len(all_blocks) if limit else 100
            page_size = min(100, remaining_limit) if limit else 100
            
            blocks_response = client.blocks.children.list(
                block_id=page_id, 
                page_size=page_size,
                start_cursor=start_cursor
            )
            
            page_blocks = blocks_response.get('results', [])
            all_blocks.extend(page_blocks)
            
            print(f"    Got {len(page_blocks)} blocks (total: {len(all_blocks)})")
            
            # If including children, get them recursively
            if include_children:
                children_count = 0
                for block in page_blocks:
                    if block.get('has_children', False):
                        block_id = block.get('id')
                        if block_id:
                            children = get_block_children_recursively(client, block_id)
                            all_blocks.extend(children)
                            children_count += len(children)
                
                if children_count > 0:
                    print(f"    Got {children_count} child blocks (total: {len(all_blocks)})")
            
            # Check if there are more blocks
            has_more = blocks_response.get('has_more', False)
            start_cursor = blocks_response.get('next_cursor')
            
            if not has_more:
                print("  No more blocks to fetch")
                break
                
            if limit and len(all_blocks) >= limit:
                break
        
        # Trim to exact limit if specified
        if limit and len(all_blocks) > limit:
            all_blocks = all_blocks[:limit]
        
        print(f"Total blocks fetched: {len(all_blocks)}")
        
        # Create output data
        output_data = {
            'page_info': {
                'id': page_id,
                'title': page_info.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled'),
                'created_time': page_info.get('created_time'),
                'last_edited_time': page_info.get('last_edited_time'),
                'url': page_info.get('url')
            },
            'scrape_info': {
                'scraped_at': datetime.now().isoformat(),
                'limit_requested': limit or 'ALL',
                'blocks_fetched': len(all_blocks),
                'pages_fetched': page_count,
                'complete_scrape': limit is None or len(all_blocks) < limit
            },
            'blocks': all_blocks
        }
        
        return output_data
        
    except Exception as e:
        print(f"Error scraping page: {e}")
        raise

def save_scraped_data(data, page_id):
    """Save scraped data to JSON file"""
    # Create scraped_pages directory if it doesn't exist
    scraped_dir = Path(__file__).parent / 'scraped_pages'
    scraped_dir.mkdir(exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"page_{page_id[:8]}_{timestamp}.json"
    filepath = scraped_dir / filename
    
    # Save to file with pretty formatting
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Scraped data saved to: {filepath}")
    return str(filepath)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Scrape blocks from a Notion page',
        epilog='Example: python scrape_page_blocks.py 24972d5af2de80769c85d11ddf288692 --limit 15 (or no --limit for all blocks)'
    )
    parser.add_argument(
        'page_id', 
        help='Notion page ID'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        default=None,
        help='Number of blocks to fetch (default: all blocks)'
    )
    parser.add_argument(
        '--no-children',
        action='store_true',
        help='Do not recursively fetch child blocks'
    )
    
    args = parser.parse_args()
    
    try:
        # Scrape the page
        include_children = not args.no_children
        scraped_data = scrape_page_blocks(args.page_id, args.limit, include_children)
        
        # Save the data
        filepath = save_scraped_data(scraped_data, args.page_id)
        
        # Show summary
        print(f"\n{'='*60}")
        print(f"SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Page ID: {args.page_id}")
        print(f"Page Title: {scraped_data['page_info']['title']}")
        print(f"Blocks Scraped: {scraped_data['scrape_info']['blocks_fetched']}")
        print(f"Complete Scrape: {scraped_data['scrape_info']['complete_scrape']}")
        print(f"Pages Fetched: {scraped_data['scrape_info']['pages_fetched']}")
        print(f"Saved to: {filepath}")
        
        # Show block types
        block_types = {}
        for block in scraped_data['blocks']:
            block_type = block.get('type', 'unknown')
            block_types[block_type] = block_types.get(block_type, 0) + 1
        
        print(f"\nBlock Types Found:")
        for block_type, count in block_types.items():
            print(f"  {block_type}: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
