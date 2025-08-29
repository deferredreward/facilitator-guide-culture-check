#!/usr/bin/env python3
"""
Page Formatter Analyzer - Quick script to examine page formatting issues

This script analyzes a Notion page to identify formatting problems and suggests improvements.
Uses existing cached data to avoid overwriting previous scrapes for before/after comparison.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from collections import Counter

# Add utils directory to path for utility imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from file_finder import find_debug_file_by_page_id_only

def analyze_page_structure(page_id):
    """
    Analyze the structure of a Notion page to identify formatting issues
    Uses existing cached data only - does not scrape to preserve before/after comparison
    
    Args:
        page_id (str): Notion page ID
    """
    print(f"Analyzing page structure for: {page_id}")
    
    # Load existing cached data only
    debug_file = find_debug_file_by_page_id_only(page_id)
    
    if not debug_file:
        print("❌ No cached data found. Run the scraper first to generate cache data.")
        print("   Use: python notion_scraper.py <page_id>")
        return
    
    print(f"Using cached data: {debug_file}")
    
    # Load the debug data
    with open(debug_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    blocks = data.get('blocks', [])
    page = data.get('page', {})
    
    print(f"Loaded {len(blocks)} blocks from cached data")
    
    # Analyze block types
    block_types = Counter()
    text_blocks = []
    long_blocks = []
    missing_types = []
    synced_issues = []
    
    for i, block in enumerate(blocks):
        block_type = block.get('type', 'unknown')
        block_types[block_type] += 1
        
        # Check for unsupported block types that cause formatting issues
        if block_type in ['column_list', 'column', 'toggle', 'callout', 'divider']:
            missing_types.append((i, block_type, block.get('id')))
        
        # Check for synced block issues
        if block_type == 'synced_block':
            synced_data = block.get('synced_block', {})
            if not synced_data or synced_data.get('synced_from') is None:
                synced_issues.append((i, block.get('id')))
        
        # Analyze text content
        text_content = extract_text_from_block(block)
        if text_content:
            text_blocks.append((i, block_type, len(text_content), text_content[:100]))
            if len(text_content) > 2000:
                long_blocks.append((i, block_type, len(text_content)))
    
    # Print analysis results
    print("\n" + "="*60)
    print("📊 PAGE STRUCTURE ANALYSIS")
    print("="*60)
    
    # Extract page title safely
    page_title = "Unknown"
    if page.get('properties'):
        name_prop = page['properties'].get('Name') or page['properties'].get('title')
        if name_prop and name_prop.get('title') and len(name_prop['title']) > 0:
            page_title = name_prop['title'][0].get('plain_text', 'Unknown')
    
    print(f"📄 Page Title: {page_title}")
    print(f"🧱 Total Blocks: {len(blocks)}")
    print(f"📝 Text Blocks: {len(text_blocks)}")
    print(f"⚠️ Long Blocks (>2000 chars): {len(long_blocks)}")
    print(f"❌ Unsupported Block Types: {len(missing_types)}")
    print(f"🔗 Synced Block Issues: {len(synced_issues)}")
    
    print("\n🏗️ BLOCK TYPE DISTRIBUTION:")
    for block_type, count in block_types.most_common():
        if block_type in ['column_list', 'column', 'toggle', 'callout', 'divider']:
            status = "❌"
        elif block_type == 'synced_block':
            status = "⚠️"
        else:
            status = "✅"
        print(f"{status} {block_type}: {count}")
    
    if long_blocks:
        print("\n⚠️ BLOCKS EXCEEDING 2000 CHARACTER LIMIT:")
        for i, block_type, length in long_blocks[:10]:  # Show first 10
            print(f"  Block {i} ({block_type}): {length} characters")
    
    if missing_types:
        print("\n❌ UNSUPPORTED BLOCK TYPES CAUSING FORMATTING ISSUES:")
        for i, block_type, block_id in missing_types[:10]:  # Show first 10
            print(f"  Block {i}: {block_type} (ID: {block_id[:8] if block_id else 'None'}...)")
    
    if synced_issues:
        print("\n🔗 SYNCED BLOCKS WITH ISSUES:")
        for i, block_id in synced_issues[:5]:  # Show first 5
            print(f"  Block {i}: (ID: {block_id[:8] if block_id else 'None'}...)")
    
    print("\n💡 RECOMMENDATIONS FOR WRITER IMPROVEMENTS:")
    
    if missing_types:
        print("1. 🚀 HIGH PRIORITY: Add support for missing block types:")
        unique_missing = set([block_type for _, block_type, _ in missing_types])
        for block_type in sorted(unique_missing):
            print(f"   - {block_type} ({sum(1 for _, bt, _ in missing_types if bt == block_type)} instances)")
    
    if long_blocks:
        print("2. ✂️ Text length fixes needed:")
        print("   - Implement text chunking for blocks >2000 chars")
        print("   - Split into multiple paragraphs automatically")
    
    if synced_issues:
        print("3. 🔗 Synced block handling:")
        print("   - Fix null reference errors in synced_block processing")
        
    if block_types['paragraph'] > 50:
        print("4. 📝 Content organization:")
        print("   - Consider grouping related paragraphs")
        print("   - Use headings to break up long sections")
    
    print("5. 🎯 Format-specific improvements:")
    print("   - Add toggle block creation for collapsible content")
    print("   - Implement column layout support")
    print("   - Add callout block styling")
    
    # Summary stats for before/after comparison
    print("\n📈 SUMMARY STATS (for before/after comparison):")
    print(f"Total blocks: {len(blocks)}")
    print(f"Supported blocks: {len(blocks) - len(missing_types)}")
    print(f"Unsupported blocks: {len(missing_types)}")
    print(f"Coverage: {((len(blocks) - len(missing_types)) / len(blocks) * 100):.1f}%")
    
def extract_text_from_block(block):
    """Extract plain text from a block, handling different block types"""
    block_type = block.get('type')
    if not block_type:
        return ""
    
    # Handle different block types
    if block_type == 'paragraph':
        rich_text = block.get('paragraph', {}).get('rich_text', [])
    elif block_type.startswith('heading_'):
        rich_text = block.get(block_type, {}).get('rich_text', [])
    elif block_type == 'bulleted_list_item':
        rich_text = block.get('bulleted_list_item', {}).get('rich_text', [])
    elif block_type == 'numbered_list_item':
        rich_text = block.get('numbered_list_item', {}).get('rich_text', [])
    elif block_type == 'to_do':
        rich_text = block.get('to_do', {}).get('rich_text', [])
    elif block_type == 'quote':
        rich_text = block.get('quote', {}).get('rich_text', [])
    else:
        return ""
    
    # Extract plain text from rich text array
    if not rich_text:
        return ""
    
    text_parts = []
    for text_part in rich_text:
        text_parts.append(text_part.get('plain_text', ''))
    
    return ''.join(text_parts)

def extract_page_id_from_url(url_or_id):
    """Extract page ID from URL or return as-is if already clean ID"""
    import re
    
    clean_input = url_or_id.strip()
    
    # If it's already a clean ID (32 chars, alphanumeric with possible dashes), return as-is
    if len(clean_input.replace('-', '')) == 32 and clean_input.replace('-', '').isalnum():
        return clean_input.replace('-', '')
    
    # Extract from URL patterns
    url_pattern = r'([a-f0-9]{8}[a-f0-9]{4}[a-f0-9]{4}[a-f0-9]{4}[a-f0-9]{12})(?:[\?#].*)?$'
    match = re.search(url_pattern, clean_input, re.IGNORECASE)
    
    if match:
        return match.group(1)
    
    return clean_input

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze Notion page formatting and structure')
    parser.add_argument('page_id', help='Notion page ID or URL')
    
    args = parser.parse_args()
    
    # Extract page ID if URL provided
    clean_page_id = extract_page_id_from_url(args.page_id)
    
    analyze_page_structure(clean_page_id)

if __name__ == "__main__":
    main()