#!/usr/bin/env python3
"""Check the parent blocks and context of target blocks"""
import os
import json
from dotenv import load_dotenv
from notion_client import Client
from notion_block_editor import get_all_blocks_recursively, extract_plain_text_from_block

load_dotenv()

page_id = "28c72d5af2de8079bf4ccf8c6e2e8401"
target_blocks = [
    "28c72d5a-f2de-8059-b89a-f822e6b2b599",
    "28c72d5a-f2de-809e-96d7-d23b7f5121a8"
]

# Also check their parents
parent_blocks = [
    "28c72d5a-f2de-80fe-94f3-c10b733d9d76",  # Parent of first target
    "28c72d5a-f2de-8080-9410-c29f3106e9a1"   # Parent of second target
]

notion_token = os.getenv('NOTION_API_KEY')
client = Client(auth=notion_token)

# Fetch all blocks
all_blocks = get_all_blocks_recursively(client, page_id, max_depth=20, debug=False)

print(f"Total blocks fetched: {len(all_blocks)}\n")

# Analyze parents
for parent_id in parent_blocks:
    print(f"{'='*60}")
    print(f"Parent block: {parent_id}")
    print(f"{'='*60}")

    parent = next((b for b in all_blocks if b.get('id') == parent_id), None)

    if not parent:
        print(f"ERROR: Parent block not found!")
        continue

    print(f"Type: {parent.get('type')}")
    print(f"Has children: {parent.get('has_children')}")

    # Extract text
    plain_text = extract_plain_text_from_block(parent)
    print(f"Text: '{plain_text[:200]}'...")

    # Find all children
    children = [b for b in all_blocks if b.get('parent', {}).get('block_id') == parent_id]
    print(f"\nChildren ({len(children)}):")
    for i, child in enumerate(children, 1):
        child_id = child.get('id')
        child_type = child.get('type')
        child_text = extract_plain_text_from_block(child)[:50]
        is_target = child_id in target_blocks
        marker = " <<< TARGET" if is_target else ""
        print(f"  {i}. [{child_type}] {child_id[:8]}... : '{child_text}'{marker}")

    print()
