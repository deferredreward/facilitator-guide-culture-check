#!/usr/bin/env python3
"""
Scan for synced blocks and provide preview info for manual unsyncing
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

def get_notion_client():
    token = os.getenv('NOTION_API_KEY')
    if not token:
        raise RuntimeError("Missing NOTION_API_KEY in environment variables")
    return Client(auth=token)

def get_page_title(client, page_id):
    """Get the title of a page"""
    try:
        page = client.pages.retrieve(page_id)
        
        # Try to get title from properties
        properties = page.get('properties', {})
        for prop_name, prop_data in properties.items():
            if prop_data.get('type') == 'title':
                title_array = prop_data.get('title', [])
                if title_array:
                    return ''.join([t.get('text', {}).get('content', '') for t in title_array])
        
        # Fallback: try to get from parent page if this is a child page
        parent = page.get('parent', {})
        if parent.get('type') == 'page_id':
            parent_page_id = parent['page_id']
            return get_page_title(client, parent_page_id)
            
        return "Untitled"
    except Exception:
        return "Unknown Page"

def extract_text_preview(block):
    """Extract first few words from a block for preview"""
    block_type = block.get('type')
    if not block_type:
        return ""
    
    type_data = block.get(block_type, {})
    rich_text = type_data.get('rich_text', [])
    
    if rich_text:
        text = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
        words = text.strip().split()
        return ' '.join(words[:5])
    
    return ""

def get_all_blocks_from_page(client, page_id):
    """Get all blocks from a page recursively"""
    blocks = []
    
    def get_blocks_recursive(block_id):
        try:
            response = client.blocks.children.list(block_id)
            page_blocks = response.get('results', [])
            
            for block in page_blocks:
                blocks.append(block)
                if block.get('has_children'):
                    get_blocks_recursive(block.get('id'))
                    
        except Exception as e:
            print(f"Error fetching blocks from {block_id}: {e}")
    
    get_blocks_recursive(page_id)
    return blocks

def scan_for_synced_blocks(page_id):
    """Scan a page for synced blocks and provide preview info"""
    client = get_notion_client()
    
    print(f"Scanning page {page_id} for synced blocks...")
    
    # Get page title
    page_title = get_page_title(client, page_id)
    print(f"Page title: {page_title}")
    print("=" * 60)
    
    # Get all blocks from the page
    all_blocks = get_all_blocks_from_page(client, page_id)
    
    # Find synced blocks
    synced_blocks = [block for block in all_blocks if block.get('type') == 'synced_block']
    
    if not synced_blocks:
        print("No synced blocks found on this page.")
        return []
    
    print(f"Found {len(synced_blocks)} synced block(s):")
    print()
    
    synced_info = []
    
    for i, block in enumerate(synced_blocks, 1):
        block_id = block.get('id')
        synced_data = block.get('synced_block', {})
        synced_from = synced_data.get('synced_from')
        
        # Determine block type
        if synced_from is None:
            block_type = "ORIGINAL"
            original_id = block_id
        else:
            block_type = "REFERENCE" 
            original_id = synced_from.get('block_id')
        
        # Try to get preview text from children
        preview_text = "No preview available"
        try:
            children_response = client.blocks.children.list(block_id)
            children = children_response.get('results', [])
            if children:
                preview_text = extract_text_preview(children[0])
                if not preview_text and len(children) > 1:
                    preview_text = extract_text_preview(children[1])
        except Exception:
            # If direct children fail, try original block children for references
            if block_type == "REFERENCE" and original_id:
                try:
                    original_children_response = client.blocks.children.list(original_id)
                    original_children = original_children_response.get('results', [])
                    if original_children:
                        preview_text = extract_text_preview(original_children[0])
                        if not preview_text and len(original_children) > 1:
                            preview_text = extract_text_preview(original_children[1])
                except Exception:
                    pass
        
        # Get context from previous and next blocks
        prev_block_text = "N/A"
        next_block_text = "N/A"
        
        # Find this block in the all_blocks list to get context
        block_index = None
        for idx, b in enumerate(all_blocks):
            if b.get('id') == block_id:
                block_index = idx
                break
        
        if block_index is not None:
            if block_index > 0:
                prev_block = all_blocks[block_index - 1]
                prev_block_text = extract_text_preview(prev_block) or f"({prev_block.get('type', 'unknown')} block)"
            
            if block_index < len(all_blocks) - 1:
                next_block = all_blocks[block_index + 1]
                next_block_text = extract_text_preview(next_block) or f"({next_block.get('type', 'unknown')} block)"
        
        info = {
            'number': i,
            'block_id': block_id,
            'type': block_type,
            'original_id': original_id,
            'preview': preview_text,
            'previous_block': prev_block_text,
            'next_block': next_block_text,
            'page_title': page_title
        }
        
        synced_info.append(info)
        
        print(f"{i}. Block ID: {block_id}")
        print(f"   Type: {block_type}")
        print(f"   Content: {preview_text}")
        print(f"   BEFORE: {prev_block_text}")
        print(f"   AFTER: {next_block_text}")
        print(f"   Page: {page_title}")
        print()
    
    return synced_info

def save_synced_blocks_info(synced_info, page_id):
    """Save synced blocks info to a JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"synced_blocks_scan_{page_id[:8]}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(synced_info, f, indent=2)
    
    print(f"Synced blocks info saved to: {filename}")
    return filename

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python synced_block_scanner.py <page_id>")
        sys.exit(1)
    
    page_id = sys.argv[1]
    synced_info = scan_for_synced_blocks(page_id)
    
    if synced_info:
        save_synced_blocks_info(synced_info, page_id)
        print(f"\nFound {len(synced_info)} synced blocks. Please manually unsync them in Notion UI before proceeding.")