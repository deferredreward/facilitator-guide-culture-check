#!/usr/bin/env python3
"""Get full JSON structure of target blocks to see database links"""
import os
import json
from dotenv import load_dotenv
from notion_client import Client
from notion_block_editor import get_all_blocks_recursively

load_dotenv()

page_id = "28c72d5af2de8079bf4ccf8c6e2e8401"
target_blocks = [
    "28c72d5a-f2de-8059-b89a-f822e6b2b599",
    "28c72d5a-f2de-809e-96d7-d23b7f5121a8"
]

notion_token = os.getenv('NOTION_API_KEY')
client = Client(auth=notion_token)

# Fetch all blocks
all_blocks = get_all_blocks_recursively(client, page_id, max_depth=20, debug=False)

print(f"Total blocks fetched: {len(all_blocks)}\n")

# Show full JSON for target blocks
for tid in target_blocks:
    print(f"{'='*60}")
    print(f"Block: {tid}")
    print(f"{'='*60}\n")

    block = next((b for b in all_blocks if b.get('id') == tid), None)

    if block:
        print(json.dumps(block, indent=2))
    else:
        print("ERROR: Block not found!")

    print("\n")
