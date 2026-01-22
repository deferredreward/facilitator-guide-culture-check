#!/usr/bin/env python3
"""Test script to check if specific blocks are being fetched"""
import os
import json
from dotenv import load_dotenv
from notion_client import Client
from notion_block_editor import get_all_blocks_recursively

load_dotenv()

page_id = "28c72d5af2de8079bf4ccf8c6e2e8401"
target_blocks = [
    "28c72d5af2de8059b89af822e6b2b599",
    "28c72d5af2de809e96d7d23b7f5121a8"
]

# Format with hyphens for Notion API format
def format_notion_id(block_id):
    """Format block ID with hyphens like Notion API"""
    if len(block_id) == 32 and '-' not in block_id:
        return f"{block_id[:8]}-{block_id[8:12]}-{block_id[12:16]}-{block_id[16:20]}-{block_id[20:]}"
    return block_id

target_blocks_formatted = [format_notion_id(bid) for bid in target_blocks]

print(f"Searching for blocks:")
for i, bid in enumerate(target_blocks):
    print(f"  {i+1}. {bid}")
    print(f"     Formatted: {target_blocks_formatted[i]}")

print(f"\nFetching all blocks from page {page_id}...")

notion_token = os.getenv('NOTION_API_KEY')
client = Client(auth=notion_token)

# Fetch all blocks
all_blocks = get_all_blocks_recursively(client, page_id, max_depth=20, debug=False)

print(f"\nTotal blocks fetched: {len(all_blocks)}")

# Search for target blocks
found_blocks = []
for block in all_blocks:
    block_id = block.get('id', '')
    if block_id in target_blocks_formatted or block_id.replace('-', '') in target_blocks:
        found_blocks.append(block)
        print(f"\nFOUND: {block_id}")
        print(f"  Type: {block.get('type')}")
        print(f"  Has children: {block.get('has_children')}")
        print(f"  Parent: {block.get('parent', {}).get('block_id', 'N/A')}")

        # Try to extract text
        block_type = block.get('type')
        if block_type in block:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            if rich_text:
                text = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
                print(f"  Text: {text[:100]}")

print(f"\n{'='*60}")
print(f"RESULTS:")
print(f"  Looking for: {len(target_blocks)} blocks")
print(f"  Found: {len(found_blocks)} blocks")
print(f"  Missing: {len(target_blocks) - len(found_blocks)} blocks")

if len(found_blocks) < len(target_blocks):
    print(f"\n❌ PROBLEM: Not all target blocks were fetched!")
    print(f"\nMissing blocks:")
    for tid in target_blocks_formatted:
        if tid not in [b.get('id') for b in found_blocks]:
            print(f"  - {tid}")
else:
    print(f"\nSUCCESS: All target blocks were fetched!")

# Save all block IDs for inspection
output_file = "all_block_ids.txt"
with open(output_file, 'w') as f:
    for block in all_blocks:
        f.write(f"{block.get('id')} - {block.get('type')}\n")
print(f"\nAll block IDs saved to: {output_file}")
