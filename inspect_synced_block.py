#!/usr/bin/env python3
"""
Deep inspection tool for synced blocks
"""

import os
import sys
import json
import logging
from dotenv import load_dotenv
from notion_client import Client

# Load environment variables
load_dotenv()

def inspect_synced_block(block_id):
    """Deep inspection of a synced block"""
    
    # Initialize Notion client
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        print("❌ NOTION_API_KEY not found in environment variables")
        return
    
    client = Client(auth=notion_token)
    
    try:
        print(f"🔍 Inspecting synced block: {block_id}")
        print("=" * 60)
        
        # 1. Get the block itself
        print("\n1. BLOCK METADATA:")
        block = client.blocks.retrieve(block_id)
        print(f"   Type: {block.get('type')}")
        print(f"   Has Children: {block.get('has_children', False)}")
        print(f"   Created: {block.get('created_time')}")
        print(f"   Last Edited: {block.get('last_edited_time')}")
        
        # 2. Examine synced block structure
        if block.get('type') == 'synced_block':
            print("\n2. SYNCED BLOCK STRUCTURE:")
            synced_data = block.get('synced_block', {})
            synced_from = synced_data.get('synced_from')
            
            if synced_from is None:
                print("   🎯 This is an ORIGINAL synced block")
                print("   📋 Content should be stored as children of this block")
            else:
                original_block_id = synced_from.get('block_id')
                print("   🔄 This is a REFERENCE synced block")
                print(f"   🎯 Points to original: {original_block_id}")
                
                # Try to get the original block
                try:
                    print("\n   Checking original block...")
                    original_block = client.blocks.retrieve(original_block_id)
                    print(f"   ✅ Original block exists: {original_block.get('type')}")
                    print(f"   📋 Original has children: {original_block.get('has_children', False)}")
                except Exception as e:
                    print(f"   ❌ Cannot access original block: {e}")
        
        # 3. Try to get children from this block
        print("\n3. DIRECT CHILDREN CHECK:")
        try:
            children_response = client.blocks.children.list(block_id)
            children = children_response.get('results', [])
            print(f"   📦 Found {len(children)} direct children")
            
            for i, child in enumerate(children[:3], 1):  # Show first 3
                child_type = child.get('type', 'unknown')
                print(f"   Child {i}: {child_type} - {child.get('id', 'no-id')[:8]}...")
                
                # Try to extract text from child
                if child_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3']:
                    rich_text = child.get(child_type, {}).get('rich_text', [])
                    if rich_text:
                        text = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
                        print(f"      Text: {text[:50]}{'...' if len(text) > 50 else ''}")
            
            if len(children) > 3:
                print(f"   ... and {len(children) - 3} more children")
                
        except Exception as e:
            print(f"   ❌ Cannot get direct children: {e}")
        
        # 4. If it's a reference block, try to get children from original
        if block.get('type') == 'synced_block':
            synced_data = block.get('synced_block', {})
            synced_from = synced_data.get('synced_from')
            
            if synced_from is not None:
                original_block_id = synced_from.get('block_id')
                print(f"\n4. ORIGINAL BLOCK CHILDREN CHECK:")
                try:
                    original_children_response = client.blocks.children.list(original_block_id)
                    original_children = original_children_response.get('results', [])
                    print(f"   📦 Found {len(original_children)} children in original block")
                    
                    for i, child in enumerate(original_children[:3], 1):  # Show first 3
                        child_type = child.get('type', 'unknown')
                        print(f"   Original Child {i}: {child_type} - {child.get('id', 'no-id')[:8]}...")
                        
                        # Try to extract text from child
                        if child_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3']:
                            rich_text = child.get(child_type, {}).get('rich_text', [])
                            if rich_text:
                                text = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
                                print(f"      Text: {text[:50]}{'...' if len(text) > 50 else ''}")
                    
                    if len(original_children) > 3:
                        print(f"   ... and {len(original_children) - 3} more children")
                        
                except Exception as e:
                    print(f"   ❌ Cannot get original block children: {e}")
        
        # 5. Save full JSON for detailed inspection
        print(f"\n5. SAVING FULL JSON:")
        output_file = f"synced_block_inspection_{block_id[:8]}.json"
        
        inspection_data = {
            "block_metadata": block,
            "direct_children": None,
            "original_children": None
        }
        
        # Get direct children
        try:
            children_response = client.blocks.children.list(block_id)
            inspection_data["direct_children"] = children_response.get('results', [])
        except Exception as e:
            inspection_data["direct_children_error"] = str(e)
        
        # Get original children if reference block
        if block.get('type') == 'synced_block':
            synced_data = block.get('synced_block', {})
            synced_from = synced_data.get('synced_from')
            if synced_from is not None:
                original_block_id = synced_from.get('block_id')
                try:
                    original_children_response = client.blocks.children.list(original_block_id)
                    inspection_data["original_children"] = original_children_response.get('results', [])
                except Exception as e:
                    inspection_data["original_children_error"] = str(e)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(inspection_data, f, indent=2, default=str)
        
        print(f"   💾 Saved detailed inspection to: {output_file}")
        print(f"   📋 Block type: {block.get('type')}")
        print(f"   🔗 Is reference: {'Yes' if synced_from is not None else 'No'}")
        
    except Exception as e:
        print(f"❌ Error inspecting block: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inspect_synced_block.py <block_id>")
        sys.exit(1)
    
    block_id = sys.argv[1]
    inspect_synced_block(block_id)