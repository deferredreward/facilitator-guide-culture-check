#!/usr/bin/env python3
"""
Fetch a synced block and all its children
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

# Load environment variables
load_dotenv()

def get_block_with_children(client, block_id, max_depth=5):
    """Get a block and all its children recursively"""
    
    def get_children_recursive(parent_id, depth=0):
        if depth >= max_depth:
            return []
        
        all_children = []
        start_cursor = None
        
        try:
            while True:
                response = client.blocks.children.list(
                    block_id=parent_id,
                    page_size=100,
                    start_cursor=start_cursor
                )
                
                children = response.get('results', [])
                
                for child in children:
                    # Add metadata
                    child['_metadata'] = {
                        'parent_id': parent_id,
                        'depth': depth + 1
                    }
                    all_children.append(child)
                    
                    # Get grandchildren if they exist
                    if child.get('has_children', False):
                        grandchildren = get_children_recursive(child.get('id'), depth + 1)
                        all_children.extend(grandchildren)
                
                if not response.get('has_more', False):
                    break
                    
                start_cursor = response.get('next_cursor')
                
        except Exception as e:
            print(f"Error getting children for {parent_id}: {e}")
        
        return all_children
    
    # Get the main block
    try:
        main_block = client.blocks.retrieve(block_id)
        main_block['_metadata'] = {
            'parent_id': 'ROOT',
            'depth': 0
        }
        
        # Get all children
        children = get_children_recursive(block_id)
        
        return {
            'main_block': main_block,
            'children': children,
            'total_blocks': 1 + len(children)
        }
        
    except Exception as e:
        print(f"Error fetching block {block_id}: {e}")
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python fetch_synced_block.py <block_id>")
        sys.exit(1)
    
    block_id = sys.argv[1]
    
    # Initialize client
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise ValueError("NOTION_API_KEY not found")
    
    client = Client(auth=notion_token)
    
    print(f"Fetching synced block: {block_id}")
    
    # Get block and children
    result = get_block_with_children(client, block_id)
    
    if not result:
        print("Failed to fetch block")
        sys.exit(1)
    
    print(f"Fetched {result['total_blocks']} blocks total")
    print(f"Main block type: {result['main_block'].get('type', 'unknown')}")
    
    # Show children summary
    if result['children']:
        child_types = {}
        for child in result['children']:
            child_type = child.get('type', 'unknown')
            child_types[child_type] = child_types.get(child_type, 0) + 1
        
        print("Children types:")
        for child_type, count in child_types.items():
            print(f"  {child_type}: {count}")
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_dir = Path('saved_blocks')
    saved_dir.mkdir(exist_ok=True)
    
    filename = f"synced_block_{block_id[:8]}_{timestamp}.json"
    filepath = saved_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to: {filepath}")

if __name__ == '__main__':
    main()