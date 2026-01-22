#!/usr/bin/env python3
"""Test why specific blocks are not being processed"""
import os
import json
from dotenv import load_dotenv
from notion_client import Client
from notion_block_editor import get_all_blocks_recursively, should_process_block, extract_plain_text_from_block

load_dotenv()

page_id = "28c72d5af2de8079bf4ccf8c6e2e8401"
target_blocks = [
    "28c72d5a-f2de-8059-b89a-f822e6b2b599",
    "28c72d5a-f2de-809e-96d7-d23b7f5121a8"
]

print(f"Fetching all blocks from page {page_id}...")

notion_token = os.getenv('NOTION_API_KEY')
client = Client(auth=notion_token)

# Fetch all blocks
all_blocks = get_all_blocks_recursively(client, page_id, max_depth=20, debug=False)

print(f"Total blocks fetched: {len(all_blocks)}\n")

# Find and analyze target blocks
for tid in target_blocks:
    print(f"{'='*60}")
    print(f"Analyzing block: {tid}")
    print(f"{'='*60}")

    block = next((b for b in all_blocks if b.get('id') == tid), None)

    if not block:
        print(f"ERROR: Block not found!")
        continue

    # Show raw block data
    print(f"\nRaw block data:")
    print(json.dumps(block, indent=2)[:500])

    # Test extraction
    plain_text = extract_plain_text_from_block(block)
    print(f"\nExtracted plain text: '{plain_text}'")
    print(f"Text length: {len(plain_text)}")
    print(f"Stripped text length: {len(plain_text.strip())}")

    # Test should_process
    should_process = should_process_block(block)
    print(f"\nshould_process_block() result: {should_process}")

    if not should_process:
        print(f"\nREASON FOR SKIPPING:")
        block_type = block.get('type', '')
        print(f"  Block type: {block_type}")

        processable_types = [
            'paragraph', 'heading_1', 'heading_2', 'heading_3',
            'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'image',
            'toggle', 'table_row', 'embed', 'to_do'
        ]

        if block_type == 'synced_block':
            print(f"  -> Block is synced_block (skipped by default)")
        elif block_type not in processable_types:
            print(f"  -> Block type '{block_type}' not in processable types")
        else:
            print(f"  -> Block has no text content (text length after strip: {len(plain_text.strip())})")

    print()

# Now check all processable blocks
print(f"\n{'='*60}")
print(f"SUMMARY OF ALL BLOCKS")
print(f"{'='*60}")

processable = [b for b in all_blocks if should_process_block(b)]
print(f"Total blocks: {len(all_blocks)}")
print(f"Processable blocks: {len(processable)}")
print(f"Skipped blocks: {len(all_blocks) - len(processable)}")

# Check if target blocks are in processable list
target_in_processable = [tid for tid in target_blocks if tid in [b.get('id') for b in processable]]
print(f"\nTarget blocks in processable list: {len(target_in_processable)}/{len(target_blocks)}")

if len(target_in_processable) < len(target_blocks):
    print(f"\nMissing from processable list:")
    for tid in target_blocks:
        if tid not in [b.get('id') for b in processable]:
            print(f"  - {tid}")
