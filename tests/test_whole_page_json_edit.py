#!/usr/bin/env python3
"""
Whole Page JSON Edit Test

This script tests editing an entire Notion page using the JSON+text AI approach.
It scrapes all blocks (including children), processes each with AI for enhancement,
and writes the updated blocks back to the page.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
from ai_handler import AIHandler

# Load environment variables
load_dotenv()

def get_all_blocks_recursively(client, page_id, max_depth=8, debug=False):
    """
    Get all blocks from a page recursively
    
    Args:
        client: Notion client
        page_id (str): Page ID
        max_depth (int): Maximum recursion depth
        debug (bool): Enable debug output
        
    Returns:
        list: All blocks with metadata
    """
    def get_children_recursive(block_id, depth=0, debug=False):
        if depth >= max_depth:
            return []
        
        all_children = []
        start_cursor = None
        
        try:
            while True:
                if debug and depth < 3:  # Only debug first few levels to avoid spam
                    print(f"    {'  ' * depth}Fetching children of {block_id[:8]}... at depth {depth}")
                
                response = client.blocks.children.list(
                    block_id=block_id,
                    page_size=100,
                    start_cursor=start_cursor
                )
                
                children = response.get('results', [])
                if debug and depth < 3:
                    print(f"    {'  ' * depth}Got {len(children)} children")
                
                for child in children:
                    child_id = child.get('id', 'unknown')
                    child_type = child.get('type', 'unknown')
                    
                    # Add metadata about hierarchy
                    child['_metadata'] = {
                        'parent_id': block_id,
                        'depth': depth
                    }
                    all_children.append(child)
                    
                    # Special logging for our target Instructions block
                    is_target_block = child_id == '25072d5a-f2de-806a-990a-c23f57158d92'
                    
                    if debug and depth < 3:
                        print(f"    {'  ' * depth}  - {child_type} {child_id[:8]} (has_children: {child.get('has_children', False)})")
                        if is_target_block:
                            print(f"    {'  ' * depth}    🎯 TARGET INSTRUCTIONS BLOCK FOUND!")
                            print(f"    {'  ' * depth}    📊 Full data: has_children={child.get('has_children')}, type={child.get('type')}, archived={child.get('archived')}")
                    
                    # Get children recursively, but skip synced blocks
                    has_children = child.get('has_children', False)
                    block_type = child.get('type')
                    is_synced = block_type == 'synced_block'
                    
                    if debug and depth < 3 and is_target_block:
                        print(f"    {'  ' * depth}    🔍 Recursion check: has_children={has_children}, is_synced={is_synced}")
                        print(f"    {'  ' * depth}    🔍 Will recurse: {has_children and not is_synced}")
                    
                    # UPDATED: Expanded secondary check for API inconsistency
                    # Check for API inconsistency - some blocks show has_children=false but actually have children
                    container_types = ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                                     'bulleted_list_item', 'numbered_list_item', 'toggle']
                    
                    needs_secondary_check = (not has_children and 
                                           block_type in container_types and
                                           depth < 3)  # Limit depth for performance
                    
                    if (has_children and not is_synced) or needs_secondary_check:
                        try:
                            if debug and depth < 3:
                                check_type = "forced API inconsistency check" if needs_secondary_check else "standard"
                                print(f"    {'  ' * depth}    ⬇️  Recursing into {child_id[:8]} ({check_type})...")
                            
                            # Try to get children
                            grandchildren = get_children_recursive(child_id, depth + 1, debug)
                            
                            if grandchildren:  # Only add if we actually found children
                                all_children.extend(grandchildren)
                                if debug and depth < 3:
                                    print(f"    {'  ' * depth}    ✅ Added {len(grandchildren)} grandchildren")
                                    if needs_secondary_check:
                                        print(f"    {'  ' * depth}    🎯 SECONDARY CHECK FOUND CHILDREN! (API inconsistency confirmed)")
                            elif needs_secondary_check and debug and depth < 3:
                                print(f"    {'  ' * depth}    ℹ️  Secondary check confirmed no children")
                                
                        except Exception as grandchild_error:
                            print(f"  ⚠️  Error getting grandchildren of {child_id[:8]} ({child_type}): {grandchild_error}")
                            if is_target_block:
                                print(f"  🎯 ❌ FAILED to get Instructions block children: {grandchild_error}")
                            # Continue processing other children even if one fails
                    elif debug and depth < 3 and is_target_block:
                        print(f"    {'  ' * depth}    ❌ NOT recursing into Instructions block: has_children={has_children}, is_synced={is_synced}")
                
                if not response.get('has_more', False):
                    break
                    
                start_cursor = response.get('next_cursor')
                
        except Exception as e:
            print(f"  ❌ Critical error getting children for {block_id[:8]}: {e}")
            # Return what we have so far instead of empty list
        
        return all_children
    
    print(f"Fetching all blocks from page: {page_id}")
    all_blocks = get_children_recursive(page_id, debug=debug)
    print(f"Found {len(all_blocks)} total blocks")
    
    return all_blocks

def extract_plain_text_from_block(block_data):
    """Extract plain text from block data"""
    block_type = block_data.get('type', '')
    
    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                     'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']:
        rich_text = block_data.get(block_type, {}).get('rich_text', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
    elif block_type == 'image':
        # Extract text from image caption
        caption = block_data.get('image', {}).get('caption', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in caption])
    
    return ""

def should_process_block(block_data):
    """Determine if a block should be processed by AI"""
    block_type = block_data.get('type', '')
    
    # Skip synced blocks (we don't recurse into them anyway)
    if block_type == 'synced_block':
        return False
    
    # Only process blocks with text content
    processable_types = [
        'paragraph', 'heading_1', 'heading_2', 'heading_3',
        'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'image'
    ]
    
    if block_type not in processable_types:
        return False
    
    # Check if block has text content
    plain_text = extract_plain_text_from_block(block_data)
    return len(plain_text.strip()) > 0

def create_json_enhancement_prompt(block_data, plain_text):
    """Create a prompt for AI enhancement"""
    return f"""You are an expert in making technical and educational content more accessible to non-native English speakers at an 8th-grade level, while preserving complex formatting structures.

You will receive a Notion block in JSON format along with its plain text. Your task is to:
1. Understand the complete formatting structure from the JSON
2. Improve the plain text content for accessibility 
3. Return a JSON response that preserves the original structure but with enhanced content

ORIGINAL BLOCK JSON:
```json
{json.dumps(block_data, indent=2)}
```

ORIGINAL PLAIN TEXT:
"{plain_text}"

ENHANCEMENT GUIDELINES:
- Simplify complex sentence structures
- Use shorter, clearer sentences  
- Replace difficult words with simpler alternatives
- Use active voice instead of passive voice
- DO NOT change technical terms, proper nouns, or key terminology
- DO NOT change time durations like "60 minutes"
- Preserve the person/tense of the original

CRITICAL: You must return a complete JSON object that:
1. Maintains the exact same structure as the input JSON
2. Only modifies the "content" fields within "text" objects in "rich_text" arrays
3. Preserves ALL formatting annotations (bold, italic, color, etc.)
4. Keeps all other fields identical (id, type, parent, timestamps, etc.)

If the content doesn't need improvement, return "NO CHANGES".

IMPROVED BLOCK JSON:"""

def process_block_with_ai(block_data, ai_handler, results_log, dry_dry_run=False):
    """Process a single block with AI"""
    block_id = block_data.get('id', 'unknown')
    block_type = block_data.get('type', 'unknown')
    
    # Extract text
    plain_text = extract_plain_text_from_block(block_data)
    
    print(f"  Processing {block_type} block {block_id[:8]}...")
    print(f"    Text: {plain_text[:50]}{'...' if len(plain_text) > 50 else ''}")
    
    # If dry-dry run, skip AI processing
    if dry_dry_run:
        print(f"    [DRY-DRY RUN] Would send to AI for enhancement")
        results_log.append({
            'block_id': block_id,
            'block_type': block_type,
            'status': 'dry_dry_run',
            'original_text': plain_text,
            'text_length': len(plain_text)
        })
        return None
    
    # Create prompt
    prompt = create_json_enhancement_prompt(block_data, plain_text)
    
    try:
        # Get AI response
        response = ai_handler.get_response(prompt, max_tokens=4000, temperature=0.3)
        
        # Check for "NO CHANGES"
        if response.strip().upper() in ['NO CHANGES', 'NO CHANGE', 'NOCHANGES']:
            print(f"    ✓ No changes needed")
            results_log.append({
                'block_id': block_id,
                'status': 'no_changes',
                'original_text': plain_text
            })
            return None
        
        # Try to parse JSON response
        if '```json' in response:
            json_start = response.find('```json') + 7
            json_end = response.find('```', json_start)
            json_str = response[json_start:json_end].strip()
        elif '{' in response and '}' in response:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
        else:
            json_str = response
            
        parsed_json = json.loads(json_str)
        
        # Extract enhanced text
        enhanced_text = extract_plain_text_from_block(parsed_json)
        
        print(f"    ✓ Enhanced: {enhanced_text[:50]}{'...' if len(enhanced_text) > 50 else ''}")
        
        results_log.append({
            'block_id': block_id,
            'status': 'enhanced',
            'original_text': plain_text,
            'enhanced_text': enhanced_text,
            'changes_made': plain_text != enhanced_text
        })
        
        return parsed_json
        
    except json.JSONDecodeError as e:
        print(f"    ✗ JSON parsing failed: {e}")
        results_log.append({
            'block_id': block_id,
            'status': 'json_error',
            'error': str(e),
            'original_text': plain_text
        })
        return None
        
    except Exception as e:
        print(f"    ✗ Processing failed: {e}")
        results_log.append({
            'block_id': block_id,
            'status': 'error',
            'error': str(e),
            'original_text': plain_text
        })
        return None

def update_block_in_notion(client, block_id, updated_block_data, dry_run=True):
    """Update a block in Notion"""
    if dry_run:
        print(f"    [DRY RUN] Would update block {block_id}")
        return True
    
    try:
        # Extract just the content part for updating
        block_type = updated_block_data.get('type')
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                         'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']:
            
            rich_text = updated_block_data.get(block_type, {}).get('rich_text', [])
            
            client.blocks.update(
                block_id=block_id,
                **{block_type: {'rich_text': rich_text}}
            )
            
            print(f"    ✓ Updated {block_type} block {block_id}")
            return True
            
        elif block_type == 'image':
            # Update image caption
            caption = updated_block_data.get('image', {}).get('caption', [])
            
            client.blocks.update(
                block_id=block_id,
                image={'caption': caption}
            )
            
            print(f"    ✓ Updated image caption {block_id}")
            return True
            
    except Exception as e:
        print(f"    ✗ Update failed: {e}")
        return False

def test_whole_page_json_edit(page_id, ai_model='claude', dry_run=True, dry_dry_run=False, limit=None):
    """Test editing a whole page with JSON approach"""
    
    # Initialize clients
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise ValueError("NOTION_API_KEY not found in environment variables")
    
    client = Client(auth=notion_token)
    ai_handler = None if dry_dry_run else AIHandler(ai_model)
    
    print(f"=== WHOLE PAGE JSON EDIT TEST ===")
    print(f"Page ID: {page_id}")
    print(f"AI Model: {ai_model if not dry_dry_run else 'NONE (dry-dry run)'}")
    print(f"Dry Run: {dry_run}")
    print(f"Dry-Dry Run (No AI): {dry_dry_run}")
    print(f"Limit: {limit or 'None'}")
    print()
    
    # Get page info
    try:
        page_info = client.pages.retrieve(page_id)
        page_title = page_info.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled')
        print(f"Page: {page_title}")
    except Exception as e:
        print(f"Error getting page info: {e}")
        return
    
    # Get all blocks
    print(f"\n1. Fetching all blocks...")
    all_blocks = get_all_blocks_recursively(client, page_id, debug=dry_dry_run)
    
    # Filter processable blocks and count skipped types
    processable_blocks = [block for block in all_blocks if should_process_block(block)]
    synced_blocks = [block for block in all_blocks if block.get('type') == 'synced_block']
    
    if limit:
        processable_blocks = processable_blocks[:limit]
    
    print(f"   Total blocks: {len(all_blocks)}")
    print(f"   Synced blocks (skipped): {len(synced_blocks)}")
    print(f"   Processable blocks: {len(processable_blocks)}")
    
    # Process blocks
    print(f"\n2. Processing blocks with AI...")
    results_log = []
    updates_made = 0
    
    for i, block in enumerate(processable_blocks, 1):
        block_id = block.get('id')
        print(f"\n   Block {i}/{len(processable_blocks)}")
        
        # Process with AI (or skip if dry-dry run)
        updated_block = process_block_with_ai(block, ai_handler, results_log, dry_dry_run)
        
        # Update in Notion if changes were made
        if updated_block:
            success = update_block_in_notion(client, block_id, updated_block, dry_run)
            if success:
                updates_made += 1
    
    # Save results
    print(f"\n3. Saving results...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path('test_results')
    results_dir.mkdir(exist_ok=True)
    
    results_data = {
        'test_info': {
            'page_id': page_id,
            'page_title': page_title,
            'ai_model': ai_model,
            'dry_run': dry_run,
            'dry_dry_run': dry_dry_run,
            'timestamp': timestamp,
            'limit': limit
        },
        'summary': {
            'total_blocks': len(all_blocks),
            'synced_blocks_skipped': len(synced_blocks),
            'processable_blocks': len(processable_blocks),
            'updates_made': updates_made,
            'no_changes': len([r for r in results_log if r['status'] == 'no_changes']),
            'errors': len([r for r in results_log if r['status'] in ['error', 'json_error']])
        },
        'detailed_results': results_log
    }
    
    results_file = results_dir / f"whole_page_edit_{page_id[:8]}_{ai_model}_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)
    
    print(f"   Results saved to: {results_file}")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Total blocks found: {len(all_blocks)}")
    print(f"Synced blocks (skipped): {len(synced_blocks)}")
    print(f"Processable blocks: {len(processable_blocks)}")
    print(f"Updates made: {updates_made}")
    print(f"No changes needed: {len([r for r in results_log if r['status'] == 'no_changes'])}")
    print(f"Errors: {len([r for r in results_log if r['status'] in ['error', 'json_error']])}")
    
    if dry_run:
        print(f"\n⚠️  This was a DRY RUN - no actual changes were made to Notion")
    else:
        print(f"\n✅ Changes have been written to Notion")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Test editing a whole Notion page using JSON+AI approach',
        epilog='Example: python test_whole_page_json_edit.py 24972d5af2de80769c85d11ddf288692 --ai claude --dry-run --limit 5'
    )
    parser.add_argument('page_id', help='Notion page ID to edit')
    parser.add_argument('--ai', default='claude', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model to use (default: claude)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Perform dry run without making actual changes')
    parser.add_argument('--live', action='store_true',
                      help='Make actual changes to Notion')
    parser.add_argument('--dry-dry-run', action='store_true',
                      help='Skip AI processing entirely, just show what would be processed')
    parser.add_argument('--limit', type=int, help='Limit number of blocks to process')
    
    args = parser.parse_args()
    
    # Determine run mode
    dry_dry_run = args.dry_dry_run
    dry_run = not args.live
    
    try:
        test_whole_page_json_edit(args.page_id, args.ai, dry_run, dry_dry_run, args.limit)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()