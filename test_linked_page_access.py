#!/usr/bin/env python3
"""Test if we can access the linked database pages"""
import os
import json
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# The linked page IDs from the mention blocks
linked_pages = [
    "20972d5a-f2de-803c-9b17-fba489ca851c",
    "20972d5a-f2de-80da-99ae-fefe8b81f504"
]

notion_token = os.getenv('NOTION_API_KEY')
client = Client(auth=notion_token)

print("Testing access to linked database pages...\n")

for page_id in linked_pages:
    print(f"{'='*60}")
    print(f"Testing page: {page_id}")
    print(f"{'='*60}")

    try:
        # Try to retrieve the page
        page_info = client.pages.retrieve(page_id)

        print(f"SUCCESS! We have access.")
        print(f"\nPage type: {page_info.get('object')}")
        print(f"Parent type: {page_info.get('parent', {}).get('type')}")

        # Try to get the title
        properties = page_info.get('properties', {})
        print(f"\nProperties found: {list(properties.keys())}")

        # Look for title property
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get('type')
            print(f"  - {prop_name}: {prop_type}")

            if prop_type == 'title':
                title_array = prop_data.get('title', [])
                if title_array:
                    title_text = ''.join([t.get('text', {}).get('content', '') for t in title_array])
                    print(f"    Title text: '{title_text}'")

        # Try to get blocks/content
        try:
            blocks_response = client.blocks.children.list(block_id=page_id)
            blocks = blocks_response.get('results', [])
            print(f"\nContent blocks: {len(blocks)} blocks found")

            if blocks:
                print(f"\nFirst 3 blocks preview:")
                for i, block in enumerate(blocks[:3], 1):
                    block_type = block.get('type')
                    print(f"  {i}. {block_type}")

                    # Try to extract text
                    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                                     'bulleted_list_item', 'numbered_list_item']:
                        rich_text = block.get(block_type, {}).get('rich_text', [])
                        text = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
                        if text:
                            print(f"     Text: {text[:100]}")
        except Exception as block_error:
            print(f"\nCouldn't fetch blocks: {block_error}")

    except Exception as e:
        print(f"FAILED! Error: {e}")
        print(f"\nLikely cause: Integration doesn't have access to this page/database")
        print(f"Solution: Share the database or page with your Notion integration")

    print("\n")

print("="*60)
print("TEST COMPLETE")
print("="*60)
