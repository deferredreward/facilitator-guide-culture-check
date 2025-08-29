#!/usr/bin/env python3
"""
Standalone Synced Block Finder

Finds synced blocks across multiple pages and provides context for manual unlinking.
Accepts a single page ID or a file with multiple page IDs.

Usage:
    python find_synced_blocks.py <page_id>
    python find_synced_blocks.py --file <file_path>
"""

import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

def get_notion_client():
    token = os.getenv('NOTION_API_KEY')
    if not token:
        raise RuntimeError("Missing NOTION_API_KEY in environment variables")
    return Client(auth=token)

def extract_page_id_from_text(text):
    """Extract page ID from various formats (URL, filename, etc.)"""
    text = text.strip()
    
    # If it's already just a page ID (32 hex chars with optional dashes)
    clean_id = text.replace('-', '')
    if len(clean_id) == 32 and all(c in '0123456789abcdef' for c in clean_id.lower()):
        return clean_id
    
    # Extract from filename format: "Something-FG-<page_id>"
    if '-' in text:
        parts = text.split('-')
        for part in reversed(parts):  # Check from end
            clean_part = part.replace('-', '')
            if len(clean_part) == 32 and all(c in '0123456789abcdef' for c in clean_part.lower()):
                return clean_part
    
    # Extract from URL format
    if 'notion.so' in text or 'notion.site' in text:
        # Find the page ID in the URL (32 hex chars)
        import re
        match = re.search(r'([a-f0-9]{32})', text.lower())
        if match:
            return match.group(1)
    
    return None

def get_page_title(client, page_id):
    """Get the title of a page"""
    try:
        # Format page ID properly
        if len(page_id) == 32:
            formatted_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
        else:
            formatted_id = page_id
            
        page = client.pages.retrieve(formatted_id)
        
        # Try to get title from properties
        properties = page.get('properties', {})
        for prop_name, prop_data in properties.items():
            if prop_data.get('type') == 'title':
                title_array = prop_data.get('title', [])
                if title_array:
                    return ''.join([t.get('text', {}).get('content', '') for t in title_array])
        
        return "Untitled"
    except Exception as e:
        return f"Error getting title: {str(e)}"

def extract_text_preview(block):
    """Extract first 5 words from a block for context"""
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

def get_all_blocks_from_page(client, page_id, recursive=True):
    """Get all blocks from a page, optionally including nested blocks"""
    try:
        # Format page ID properly
        if len(page_id) == 32:
            formatted_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
        else:
            formatted_id = page_id
            
        if recursive:
            # Get all blocks recursively to find nested synced blocks
            all_blocks = []
            
            def get_blocks_recursive(block_id, depth=0):
                if depth > 10:  # Prevent infinite recursion
                    return
                
                try:
                    response = client.blocks.children.list(block_id)
                    blocks = response.get('results', [])
                    
                    for block in blocks:
                        all_blocks.append(block)
                        
                        # Recurse into children if they exist
                        if block.get('has_children'):
                            get_blocks_recursive(block.get('id'), depth + 1)
                            
                except Exception as e:
                    if depth == 0:  # Only log top-level errors
                        print(f"    Error fetching blocks: {e}")
            
            get_blocks_recursive(formatted_id)
            print(f"    📊 Found {len(all_blocks)} total blocks (including nested)")
            return all_blocks
        else:
            # Just top-level blocks
            response = client.blocks.children.list(formatted_id)
            return response.get('results', [])
            
    except Exception as e:
        print(f"    Error fetching blocks from {page_id[:8]}...: {e}")
        return []

def find_context_blocks_in_hierarchy(all_blocks, synced_block_id):
    """Find blocks with text content before and after the synced block in a flattened list"""
    before_text = "N/A"
    after_text = "N/A"
    synced_index = -1
    
    # Find the synced block in the flattened list
    for i, block in enumerate(all_blocks):
        if block.get('id') == synced_block_id:
            synced_index = i
            break
    
    if synced_index == -1:
        return before_text, after_text
    
    # Search backwards for text content
    for i in range(synced_index - 1, -1, -1):
        text = extract_text_preview(all_blocks[i])
        if text.strip():
            before_text = text
            break
    
    # Search forwards for text content  
    for i in range(synced_index + 1, len(all_blocks)):
        text = extract_text_preview(all_blocks[i])
        if text.strip():
            after_text = text
            break
    
    return before_text, after_text

def find_synced_blocks_on_page(client, page_id):
    """Find all synced blocks on a single page with context"""
    page_title = get_page_title(client, page_id)
    all_blocks = get_all_blocks_from_page(client, page_id)
    
    if not all_blocks:
        return []
    
    synced_blocks_info = []
    
    for i, block in enumerate(all_blocks):
        if block.get('type') == 'synced_block':
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
            
            # Get context blocks with text
            before_text, after_text = find_context_blocks_in_hierarchy(all_blocks, block_id)
            
            synced_blocks_info.append({
                'page_id': page_id,
                'page_title': page_title,
                'block_id': block_id,
                'block_type': block_type,
                'original_id': original_id,
                'before_text': before_text,
                'after_text': after_text,
                'position': i + 1,
                'total_blocks': len(all_blocks)
            })
    
    return synced_blocks_info

def process_page_ids(page_ids):
    """Process multiple page IDs and find all synced blocks"""
    client = get_notion_client()
    all_synced_blocks = []
    
    for page_id in page_ids:
        # Get title first to show full context
        page_title = get_page_title(client, page_id)
        print(f"🔍 Scanning page: {page_title} ({page_id[:8]}...)")
        
        synced_blocks = find_synced_blocks_on_page(client, page_id)
        all_synced_blocks.extend(synced_blocks)
        
        if synced_blocks:
            print(f"   ✅ Found {len(synced_blocks)} synced blocks")
        else:
            print(f"   ❌ No synced blocks found")
    
    return all_synced_blocks

def save_results(synced_blocks):
    """Save results to JSON and print summary"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"synced_blocks_found_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(synced_blocks, f, indent=2)
    
    print(f"\n📄 Results saved to: {filename}")
    return filename

def print_summary(synced_blocks):
    """Print a human-readable summary"""
    if not synced_blocks:
        print("\n✅ No synced blocks found across all pages!")
        return
    
    print(f"\n⚠️ FOUND {len(synced_blocks)} SYNCED BLOCKS")
    print("="*80)
    
    for i, sb in enumerate(synced_blocks, 1):
        print(f"{i}. {sb['block_type']} Block")
        print(f"   Page: {sb['page_title']}")
        print(f"   Position: {sb['position']}/{sb['total_blocks']}")
        print(f"   Block ID: {sb['block_id']}")
        if sb['block_type'] == 'REFERENCE':
            print(f"   Original ID: {sb['original_id']}")
        print(f"   BEFORE: \"{sb['before_text']}\"")
        print(f"   AFTER:  \"{sb['after_text']}\"")
        print()

def main():
    parser = argparse.ArgumentParser(description='Find synced blocks across Notion pages')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('page_id', nargs='?', help='Single page ID or URL')
    group.add_argument('--file', '-f', help='File containing page IDs (one per line)')
    
    args = parser.parse_args()
    
    page_ids = []
    
    if args.page_id:
        # Single page ID
        extracted_id = extract_page_id_from_text(args.page_id)
        if not extracted_id:
            print(f"❌ Could not extract page ID from: {args.page_id}")
            sys.exit(1)
        page_ids = [extracted_id]
        
    elif args.file:
        # Multiple page IDs from file
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    extracted_id = extract_page_id_from_text(line)
                    if extracted_id:
                        page_ids.append(extracted_id)
                    else:
                        print(f"⚠️ Could not extract page ID from: {line}")
        except FileNotFoundError:
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
    
    if not page_ids:
        print("❌ No valid page IDs found")
        sys.exit(1)
    
    print(f"🚀 Processing {len(page_ids)} pages...")
    synced_blocks = process_page_ids(page_ids)
    
    save_results(synced_blocks)
    print_summary(synced_blocks)

if __name__ == "__main__":
    main()