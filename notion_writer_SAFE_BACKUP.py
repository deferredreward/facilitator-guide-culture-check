#!/usr/bin/env python3
"""
Notion Writer Module

This module provides functionality to write back to Notion pages,
including finding specific blocks and updating their content.
"""

import os
import sys
import json
import logging
import re
from pathlib import Path
from notion_client import Client
from dotenv import load_dotenv
import time
from datetime import datetime

# Add utils directory to path for utility imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from file_finder import find_debug_file_by_page_id_only

# Load environment variables
load_dotenv()

def load_prompt_from_file(prompt_name):
    """Load a specific prompt from prompts.txt file"""
    try:
        prompts_file = Path(__file__).parent / 'prompts.txt'
        if not prompts_file.exists():
            logging.warning("⚠️ prompts.txt file not found")
            return None
            
        with open(prompts_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Find the prompt section (handle optional colon)
        pattern = rf'# {re.escape(prompt_name)}:?\s*\n"""(.*?)"""'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            prompt_text = match.group(1).strip()
            logging.info(f"✅ Loaded prompt: {prompt_name}")
            return prompt_text
        else:
            logging.warning(f"⚠️ Prompt '{prompt_name}' not found in prompts.txt")
            return None
            
    except Exception as e:
        logging.error(f"❌ Error loading prompt '{prompt_name}': {e}")
        return None

class NotionWriter:
    """Handler for writing back to Notion pages"""
    
    def __init__(self):
        """Initialize Notion client"""
        self.notion_token = os.getenv('NOTION_API_KEY')
        if not self.notion_token:
            raise ValueError("NOTION_API_KEY not found in environment variables")
        
        try:
            self.client = Client(auth=self.notion_token)
            logging.info("✅ Notion writer client initialized successfully")
        except Exception as e:
            logging.error(f"❌ Failed to initialize Notion client: {e}")
            raise
    
    def _load_cached_blocks(self, page_id):
        """
        Load cached blocks from the debug JSON file if available
        
        Args:
            page_id (str): The Notion page ID
            
        Returns:
            list: List of blocks or None if cached data not available
        """
        try:
            debug_file = find_debug_file_by_page_id_only(page_id)
            
            if not debug_file:
                logging.warning(f"⚠️ No cached data found for page_id: {page_id}")
                return None
            
            with open(debug_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            blocks = cached_data.get('blocks', [])
            logging.info(f"✅ Loaded {len(blocks)} blocks from cached data")
            return blocks
            
        except Exception as e:
            logging.warning(f"⚠️ Error loading cached blocks: {e}")
            return None
    
    def find_blocks_by_criteria(self, page_id, criteria_func):
        """
        Find blocks that match a specific criteria function
        
        Args:
            page_id (str): The Notion page ID
            criteria_func (callable): Function that takes a block and returns True if it matches
            
        Returns:
            list: List of matching blocks with their content
        """
        try:
            # Try to use cached data first
            all_blocks = self._load_cached_blocks(page_id)
            
            if all_blocks is None:
                # Fall back to API calls if no cached data
                logging.info("📡 No cached data available, falling back to API calls...")
                all_blocks = self._get_all_blocks_recursively(page_id)
            else:
                logging.info("🗂️ Using cached block data (much faster!)")
            
            matching_blocks = []
            
            for block in all_blocks:
                if criteria_func(block):
                    matching_blocks.append(block)
            
            return matching_blocks
            
        except Exception as e:
            logging.error(f"❌ Error finding blocks: {e}")
            raise
    
    def find_blocks_starting_with_emoji(self, page_id, emoji):
        """
        Find blocks that start with a specific emoji
        
        Args:
            page_id (str): The Notion page ID
            emoji (str): The emoji to search for at the start of blocks
            
        Returns:
            list: List of matching blocks
        """
        def criteria_func(block):
            # Check different block types for text content
            block_type = block.get('type')
            if not block_type:
                return False
                
            # Extract text based on block type
            text_content = self._extract_plain_text_from_block(block)
            if text_content and text_content.strip().startswith(emoji):
                return True
            return False
        
        return self.find_blocks_by_criteria(page_id, criteria_func)
    
    def _extract_plain_text_from_block(self, block):
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
        elif block_type == 'callout':
            rich_text = block.get('callout', {}).get('rich_text', [])
        elif block_type == 'toggle':
            rich_text = block.get('toggle', {}).get('rich_text', [])
        elif block_type == 'image':
            rich_text = block.get('image', {}).get('caption', [])
        elif block_type == 'video':
            rich_text = block.get('video', {}).get('caption', [])
        elif block_type == 'file':
            rich_text = block.get('file', {}).get('caption', [])
        elif block_type == 'pdf':
            rich_text = block.get('pdf', {}).get('caption', [])
        elif block_type == 'audio':
            rich_text = block.get('audio', {}).get('caption', [])
        elif block_type == 'bookmark':
            rich_text = block.get('bookmark', {}).get('caption', [])
        else:
            return ""
        
        # Extract plain text from rich text array
        if not rich_text:
            return ""
        
        text_parts = []
        for text_part in rich_text:
            text_parts.append(text_part.get('plain_text', ''))
        
        return ''.join(text_parts)
    
    def _get_rich_text_from_block(self, block, block_type):
        """Extract rich text array from a block"""
        if block_type == 'paragraph':
            return block.get('paragraph', {}).get('rich_text', [])
        elif block_type.startswith('heading_'):
            return block.get(block_type, {}).get('rich_text', [])
        elif block_type == 'bulleted_list_item':
            return block.get('bulleted_list_item', {}).get('rich_text', [])
        elif block_type == 'numbered_list_item':
            return block.get('numbered_list_item', {}).get('rich_text', [])
        elif block_type == 'to_do':
            return block.get('to_do', {}).get('rich_text', [])
        elif block_type == 'quote':
            return block.get('quote', {}).get('rich_text', [])
        elif block_type == 'callout':
            return block.get('callout', {}).get('rich_text', [])
        elif block_type == 'toggle':
            return block.get('toggle', {}).get('rich_text', [])
        elif block_type == 'image':
            return block.get('image', {}).get('caption', [])
        elif block_type == 'video':
            return block.get('video', {}).get('caption', [])
        elif block_type == 'file':
            return block.get('file', {}).get('caption', [])
        elif block_type == 'pdf':
            return block.get('pdf', {}).get('caption', [])
        elif block_type == 'audio':
            return block.get('audio', {}).get('caption', [])
        elif block_type == 'bookmark':
            return block.get('bookmark', {}).get('caption', [])
        return []
    
    def _map_enhanced_text_to_structure(self, enhanced_text, existing_rich_text, original_text):
        """Map enhanced text to existing rich text structure preserving formatting"""
        # If the enhanced text is very similar to original, try to preserve structure
        if len(enhanced_text) > 0 and len(original_text) > 0:
            # Calculate similarity ratio (simple approach)
            similarity = len(set(enhanced_text.lower().split()) & set(original_text.lower().split())) / max(len(enhanced_text.split()), len(original_text.split()))
            
            if similarity > 0.6:  # If texts are similar enough, preserve some formatting
                # Try to map enhanced text to existing structure
                return self._preserve_formatting_structure(enhanced_text, existing_rich_text)
        
        # Fallback: create simple structure
        return [
            {
                "type": "text",
                "text": {
                    "content": enhanced_text
                }
            }
        ]
    
    def _preserve_formatting_structure(self, enhanced_text, existing_rich_text):
        """Attempt to preserve some formatting when updating text"""
        # Simple approach: if first part of existing text has formatting, preserve it
        if existing_rich_text and len(existing_rich_text) > 0:
            first_part = existing_rich_text[0]
            if first_part.get('annotations', {}):
                # If the first part has formatting, keep some of it
                words = enhanced_text.split()
                if words:
                    first_word_length = min(len(words[0]), 50)  # Limit formatting to reasonable length
                    
                    result = [
                        {
                            "type": "text",
                            "text": {
                                "content": enhanced_text[:first_word_length]
                            },
                            "annotations": first_part.get('annotations', {})
                        }
                    ]
                    
                    if len(enhanced_text) > first_word_length:
                        result.append({
                            "type": "text",
                            "text": {
                                "content": enhanced_text[first_word_length:]
                            }
                        })
                    
                    return result
        
        # Default fallback
        return [
            {
                "type": "text",
                "text": {
                    "content": enhanced_text
                }
            }
        ]
    
    def _preserve_links_and_mentions(self, enhanced_text, existing_rich_text):
        """Preserve links and mentions from existing rich text"""
        result = []
        
        # Look for existing links and mentions in the rich text
        existing_links = []
        for rt in existing_rich_text:
            if rt.get('type') in ['mention', 'text']:
                if rt.get('text', {}).get('link') or rt.get('mention'):
                    existing_links.append(rt)
        
        # If we have links to preserve, try to maintain them
        if existing_links and len(enhanced_text) > 10:
            # Simple approach: add enhanced text then preserve one key link
            result.append({
                "type": "text",
                "text": {
                    "content": enhanced_text
                }
            })
            
            # Add preserved link at the end if it makes sense
            if existing_links:
                result.append({
                    "type": "text",
                    "text": {"content": " "}
                })
                result.append(existing_links[0])  # Preserve first important link
            
            return result
        
        return [
            {
                "type": "text",
                "text": {
                    "content": enhanced_text
                }
            }
        ]
    
    def update_block_text(self, block_id, new_text):
        """
        Legacy method - now calls the structure-preserving version
        
        Args:
            block_id (str): The block ID to update
            new_text (str): The new text content
            
        Returns:
            dict: The updated block response
        """
        return self.update_block_text_preserving_structure(block_id, new_text, "")
    
    def reverse_words_in_text(self, text):
        """
        Reverse each word in the text while keeping word order
        
        Args:
            text (str): The original text
            
        Returns:
            str: Text with each word reversed
        """
        import re
        
        # Split into words while preserving whitespace and punctuation
        words = re.findall(r'\S+|\s+', text)
        
        reversed_words = []
        for word in words:
            if word.strip():  # If it's not just whitespace
                # Separate word from punctuation
                word_match = re.match(r'^(\W*)(.*?)(\W*)$', word)
                if word_match:
                    prefix, core_word, suffix = word_match.groups()
                    if core_word:
                        reversed_word = prefix + core_word[::-1] + suffix
                    else:
                        reversed_word = word
                else:
                    reversed_word = word[::-1]
                reversed_words.append(reversed_word)
            else:
                reversed_words.append(word)  # Keep whitespace as-is
        
        return ''.join(reversed_words)
    
    def update_block_text_preserving_structure(self, block_id, enhanced_text, original_text):
        """
        Update a block's text content while preserving rich text structure
        
        Args:
            block_id (str): The block ID to update
            enhanced_text (str): The enhanced plain text content
            original_text (str): The original plain text for comparison
            
        Returns:
            dict: The updated block response
        """
        try:
            # Get the current block to preserve its structure
            current_block = self.client.blocks.retrieve(block_id)
            block_type = current_block.get('type')
            
            if not block_type:
                raise ValueError(f"Could not determine block type for {block_id}")
            
            # Get existing rich text structure
            existing_rich_text = self._get_rich_text_from_block(current_block, block_type)
            
            # Create enhanced rich text preserving structure when possible
            if existing_rich_text and len(existing_rich_text) > 1:
                # Try to preserve formatting by intelligent mapping
                new_rich_text = self._map_enhanced_text_to_structure(enhanced_text, existing_rich_text, original_text)
            else:
                # Simple case: create new rich text array
                new_rich_text = [
                    {
                        "type": "text",
                        "text": {
                            "content": enhanced_text
                        }
                    }
                ]
            
            # Create update payload based on block type
            if block_type == 'paragraph':
                update_data = {
                    "paragraph": {
                        "rich_text": new_rich_text
                    }
                }
            elif block_type.startswith('heading_'):
                update_data = {
                    block_type: {
                        "rich_text": new_rich_text
                    }
                }
            elif block_type == 'bulleted_list_item':
                update_data = {
                    "bulleted_list_item": {
                        "rich_text": new_rich_text
                    }
                }
            elif block_type == 'numbered_list_item':
                update_data = {
                    "numbered_list_item": {
                        "rich_text": new_rich_text
                    }
                }
            elif block_type == 'to_do':
                # Preserve the checked state
                checked = current_block.get('to_do', {}).get('checked', False)
                update_data = {
                    "to_do": {
                        "rich_text": new_rich_text,
                        "checked": checked
                    }
                }
            elif block_type == 'quote':
                update_data = {
                    "quote": {
                        "rich_text": new_rich_text
                    }
                }
            else:
                raise ValueError(f"Unsupported block type for updating: {block_type}")
            
            # HARD GUARD: never modify synced blocks or their children
            try:
                if block_type == 'synced_block' or self._is_block_or_ancestor_synced_api(block_id):
                    logging.warning(f"🚫 PROTECTED: Skipping update for synced content {block_id[:8]}...")
                    return {"skipped": True, "reason": "Synced content"}
            except Exception:
                # If guard fails, be conservative and skip
                logging.warning(f"⚠️ Guard failed, conservatively skipping block {block_id[:8]}")
                return {"skipped": True, "reason": "Guard failure"}

            # Update the block
            response = self.client.blocks.update(block_id, **update_data)
            logging.info(f"✅ Block {block_id} updated successfully")
            return response
            
        except Exception as e:
            logging.error(f"❌ Error updating block {block_id}: {e}")
            raise
    
    def _get_all_blocks_recursively(self, block_id, limit=None):
        """
        Recursively get all blocks including nested children (fallback for when cached data isn't available)
        
        Args:
            block_id (str): The block ID to start from
            limit (int): Optional limit on total blocks to fetch
            
        Returns:
            list: List of all blocks
        """
        if limit:
            logging.warning(f"⚠️ Using limited API calls to get {limit} blocks - much faster!")
        else:
            logging.warning("⚠️ Using API calls to get blocks - this is slower than using cached data")
        all_blocks = []
        
        def get_blocks(b_id):
            # Early termination if we've hit the limit
            if limit and len(all_blocks) >= limit:
                return
                
            try:
                blocks_response = self.client.blocks.children.list(b_id)
                for block in blocks_response['results']:
                    all_blocks.append(block)
                    # If block has children AND is not a child_page, recurse
                    if block.get('has_children') and block.get('type') != 'child_page':
                        get_blocks(block['id'])
            except Exception as e:
                logging.warning(f"⚠️ Could not retrieve children for block {b_id}: {e}")
        
        get_blocks(block_id)
        return all_blocks
    
    def process_question_block_reversal(self, page_id, emoji="❓"):
        """
        Find blocks starting with the specified emoji and reverse all words
        
        Args:
            page_id (str): The Notion page ID
            emoji (str): The emoji to search for (default: ❓)
            
        Returns:
            dict: Results of the operation
        """
        try:
            logging.info(f"🔍 Looking for blocks starting with '{emoji}' in page {page_id}")
            
            # Find blocks starting with the emoji
            matching_blocks = self.find_blocks_starting_with_emoji(page_id, emoji)
            
            if not matching_blocks:
                logging.warning(f"⚠️ No blocks found starting with '{emoji}'")
                return {
                    "success": False,
                    "message": f"No blocks found starting with '{emoji}'",
                    "blocks_processed": 0
                }
            
            logging.info(f"✅ Found {len(matching_blocks)} blocks starting with '{emoji}'")
            
            results = []
            for block in matching_blocks:
                try:
                    # Get original text
                    original_text = self._extract_plain_text_from_block(block)
                    
                    # Reverse words in the text
                    reversed_text = self.reverse_words_in_text(original_text)
                    
                    # Update the block
                    updated_block = self.update_block_text(block['id'], reversed_text)
                    
                    results.append({
                        "block_id": block['id'],
                        "original_text": original_text,
                        "reversed_text": reversed_text,
                        "success": True
                    })
                    
                    logging.info(f"✅ Updated block {block['id']}")
                    logging.info(f"   Original: {original_text}")
                    logging.info(f"   Reversed: {reversed_text}")
                    
                except Exception as e:
                    logging.error(f"❌ Error processing block {block['id']}: {e}")
                    results.append({
                        "block_id": block['id'],
                        "success": False,
                        "error": str(e)
                    })
            
            successful_updates = sum(1 for r in results if r.get('success'))
            
            return {
                "success": True,
                "message": f"Processed {len(results)} blocks, {successful_updates} successful",
                "blocks_processed": len(results),
                "successful_updates": successful_updates,
                "results": results
            }
            
        except Exception as e:
            logging.error(f"❌ Error in process_question_block_reversal: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "blocks_processed": 0
            }
    
    def append_blocks_to_page(self, page_id, new_blocks_data):
        """
        Append new blocks to the end of a page
        
        Args:
            page_id (str): The Notion page ID
            new_blocks_data (list): List of block data dictionaries to append
            
        Returns:
            dict: Results of the append operation
        """
        try:
            response = self.client.blocks.children.append(page_id, children=new_blocks_data)
            logging.info(f"✅ Appended {len(new_blocks_data)} blocks to page {page_id}")
            return {
                'success': True,
                'blocks_added': len(new_blocks_data),
                'response': response
            }
        except Exception as e:
            logging.error(f"❌ Error appending blocks to page {page_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_added': 0
            }
    
    def insert_blocks_after(self, parent_id, new_blocks_data, after_block_id=None):
        """
        Insert new blocks after a specific block
        
        Args:
            parent_id (str): The parent block or page ID
            new_blocks_data (list): List of block data dictionaries to insert
            after_block_id (str): Block ID to insert after (if None, appends to end)
            
        Returns:
            dict: Results of the insert operation
        """
        try:
            if after_block_id:
                # Get all children of the parent
                children_response = self.client.blocks.children.list(parent_id)
                all_children = children_response['results']
                
                # Find the position of the target block
                target_index = -1
                for i, child in enumerate(all_children):
                    if child['id'] == after_block_id:
                        target_index = i
                        break
                
                if target_index == -1:
                    logging.warning(f"⚠️ Target block {after_block_id} not found, appending to end")
                    return self.append_blocks_to_page(parent_id, new_blocks_data)
                
                # For now, we'll append to the end since Notion API doesn't support insertion at specific positions
                # This is a limitation of the Notion API
                logging.info(f"📝 Inserting blocks after block {after_block_id} (appending to end due to API limitation)")
                return self.append_blocks_to_page(parent_id, new_blocks_data)
            else:
                return self.append_blocks_to_page(parent_id, new_blocks_data)
                
        except Exception as e:
            logging.error(f"❌ Error inserting blocks: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_added': 0
            }
    
    def create_heading_block(self, text, level=2):
        """
        Create a heading block data structure
        
        Args:
            text (str): Heading text
            level (int): Heading level (1, 2, or 3)
            
        Returns:
            dict: Block data for heading
        """
        heading_type = f"heading_{level}"
        return {
            "object": "block",
            "type": heading_type,
            heading_type: {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ]
            }
        }
    
    def create_paragraph_block(self, text):
        """
        Create a paragraph block data structure
        
        Args:
            text (str): Paragraph text
            
        Returns:
            dict: Block data for paragraph
        """
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ]
            }
        }
    
    def create_toggle_block(self, title, content_blocks=None):
        """
        Create a toggle block data structure
        
        Args:
            title (str): Toggle title
            content_blocks (list): List of child blocks (optional)
            
        Returns:
            dict: Block data for toggle
        """
        toggle_block = {
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }
        
        if content_blocks:
            toggle_block["toggle"]["children"] = content_blocks
        
        return toggle_block
    
    def create_callout_block(self, text, emoji="📝", color="default"):
        """
        Create a callout block data structure
        
        Args:
            text (str): Callout text
            emoji (str): Callout icon emoji
            color (str): Callout color
            
        Returns:
            dict: Block data for callout
        """
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ],
                "icon": {
                    "type": "emoji",
                    "emoji": emoji
                },
                "color": color
            }
        }
    
    def create_divider_block(self):
        """
        Create a divider block data structure
        
        Returns:
            dict: Block data for divider
        """
        return {
            "object": "block",
            "type": "divider",
            "divider": {}
        }
    
    def create_column_list_block(self, columns):
        """
        Create a column list block with column children
        
        Args:
            columns (list): List of column block data
            
        Returns:
            dict: Block data for column list
        """
        return {
            "object": "block",
            "type": "column_list",
            "column_list": {
                "children": columns
            }
        }
    
    def create_column_block(self, content_blocks):
        """
        Create a column block with content
        
        Args:
            content_blocks (list): List of blocks to put in the column
            
        Returns:
            dict: Block data for column
        """
        return {
            "object": "block",
            "type": "column",
            "column": {
                "children": content_blocks
            }
        }
    
    def create_bulleted_list_item_block(self, text, rich_text=None):
        """
        Create a bulleted list item block data structure
        
        Args:
            text (str): List item text
            
        Returns:
            dict: Block data for bulleted list item
        """
        if rich_text is None:
            rich_text = [
                {
                    "type": "text",
                    "text": {
                        "content": text
                    }
                }
            ]
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": rich_text
            }
        }
    
    def create_table_block(self, table_width, has_column_header=True, has_row_header=False, children=None):
        """
        Create a table block data structure
        
        Args:
            table_width (int): Number of columns in the table
            has_column_header (bool): Whether first row is a header
            has_row_header (bool): Whether first column is a header
            children (list): Optional list of table_row blocks
            
        Returns:
            dict: Block data for table
        """
        table_block = {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": table_width,
                "has_column_header": has_column_header,
                "has_row_header": has_row_header
            }
        }
        
        # Add children if provided
        if children:
            table_block["table"]["children"] = children
            
        return table_block
    
    def create_table_row_block(self, cells):
        """
        Create a table row block data structure
        
        Args:
            cells (list): List of cell contents (strings)
            
        Returns:
            dict: Block data for table row
        """
        rich_cells = []
        for cell in cells:
            if isinstance(cell, str):
                rich_cells.append(self._markdown_to_rich_text(cell))
            else:
                rich_cells.append(cell)  # Assume it's already rich text
        
        return {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": rich_cells
            }
        }
    
    def parse_markdown_table(self, lines, start_idx):
        """
        Parse markdown table starting at start_idx and return table block with rows
        
        Args:
            lines (list): List of markdown lines
            start_idx (int): Index where table starts
            
        Returns:
            tuple: (table_block, next_line_idx)
        """
        table_rows = []
        i = start_idx
        
        while i < len(lines):
            line = lines[i].strip()
            if not line.startswith('|') or not line.endswith('|'):
                break
            
            # Skip separator lines (|---|---|---|) - more robust pattern
            if re.match(r'^\|[\s\-\|:]+\|?$', line) and '--' in line:
                logging.info(f"🔧 Skipping table separator line: {line}")
                i += 1
                continue
                
            # Parse table row
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
            if cells:
                table_rows.append(cells)
            i += 1
        
        if not table_rows:
            return None, start_idx + 1
            
        # Create table block with special metadata for later processing
        num_columns = len(table_rows[0]) if table_rows else 1
        table_block = self.create_table_block(num_columns, has_column_header=True)
        
        # Store table rows for later API calls (can't add children directly to table block)
        table_block["_table_rows"] = table_rows
        table_block["_needs_special_handling"] = True
        
        return table_block, i

    def _markdown_to_rich_text(self, text: str):
        """Convert simple markdown (**bold**, *italic*, `code`) to Notion rich_text array."""
        parts = re.split(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)", text)
        rich = []
        for part in parts:
            if not part:
                continue
            ann = {
                'bold': False,
                'italic': False,
                'strikethrough': False,
                'underline': False,
                'code': False,
                'color': 'default'
            }
            content = part
            if part.startswith('**') and part.endswith('**') and len(part) >= 4:
                content = part[2:-2]
                ann['bold'] = True
            elif part.startswith('`') and part.endswith('`') and len(part) >= 2:
                content = part[1:-1]
                ann['code'] = True
            elif part.startswith('*') and part.endswith('*') and len(part) >= 2:
                content = part[1:-1]
                ann['italic'] = True
            if content:
                rich.append({
                    'type': 'text',
                    'text': {'content': content},
                    'annotations': ann
                })
        return rich if rich else [{"type": "text", "text": {"content": text}}]

    def parse_markdown_to_blocks(self, markdown_text):
        """
        Parse markdown text into Notion block structures
        
        Args:
            markdown_text (str): Markdown text to parse
            
        Returns:
            list: List of Notion block data structures
        """
        blocks = []
        lines = markdown_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Check for table start
            if line.startswith('|') and line.endswith('|'):
                table_block, next_i = self.parse_markdown_table(lines, i)
                if table_block:
                    blocks.append(table_block)
                    i = next_i
                    continue
                
            # Handle headings
            if line.startswith('### '):
                blocks.append(self.create_heading_block(line[4:], 3))
            elif line.startswith('## '):
                # Skip creating heading blocks for ## (used for parsing structure only)
                pass
            elif line.startswith('# '):
                blocks.append(self.create_heading_block(line[2:], 1))
            # Handle special formatting
            elif line.strip() == '---':
                blocks.append(self.create_divider_block())
            elif line.startswith('> '):
                # Treat as callout
                blocks.append(self.create_callout_block(line[2:], "📝", "gray_background"))
            # Handle bullet points
            elif line.startswith('- ') or line.startswith('• ') or line.startswith('* '):
                content = line[2:]
                # If bullet is just a bold label like **Cultural Strengths:**, make it a heading
                m = re.match(r"^\*\*(.+?)\*\*:?$", content)
                if m:
                    blocks.append(self.create_heading_block(m.group(1), 3))
                else:
                    rich = self._markdown_to_rich_text(content)
                    blocks.append(self.create_bulleted_list_item_block(content, rich_text=rich))
            # Handle numbered lists (convert to bullets for simplicity)
            elif re.match(r'^\d+\. ', line):
                text = line.split('. ', 1)[1] if '. ' in line else line
                rich = self._markdown_to_rich_text(text)
                blocks.append(self.create_bulleted_list_item_block(text, rich_text=rich))
            # Regular paragraph
            else:
                if line.strip():  # Only create non-empty paragraphs
                    rich = self._markdown_to_rich_text(line)
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich}
                    })
            
            i += 1
        
        return blocks
    
    def find_activity_toggle_blocks(self, page_id):
        """
        Find toggle blocks containing the word 'activity' - these contain cultural activities
        
        Args:
            page_id (str): The Notion page ID
            
        Returns:
            list: List of toggle blocks that contain activities
        """
        def is_activity_toggle(block):
            if block.get('type') != 'toggle':
                return False
                
            text_content = self._extract_plain_text_from_block(block)
            if not text_content:
                return False
                
            return 'activity' in text_content.lower()
        
        activity_toggles = self.find_blocks_by_criteria(page_id, is_activity_toggle)
        logging.info(f"🌯 Found {len(activity_toggles)} activity toggle blocks")
        
        return activity_toggles

    def _heading_level_from_type(self, block_type: str) -> int:
        if block_type == 'heading_1':
            return 1
        if block_type == 'heading_2':
            return 2
        if block_type == 'heading_3':
            return 3
        return 99

    def find_activity_heading_blocks(self, page_id):
        """Find heading blocks whose text contains 'activity' (case-insensitive)."""
        def is_activity_heading(block):
            btype = block.get('type')
            if not btype or not btype.startswith('heading_'):
                return False
            text = self._extract_plain_text_from_block(block) or ''
            return 'activity' in text.lower()
        return self.find_blocks_by_criteria(page_id, is_activity_heading)

    def find_activity_sections(self, page_id):
        """Build activity sections from toggles and headings.

        Returns a list of dicts: { 'container_id': str, 'label': str, 'content_text': str }
        where container_id is where we can append a cultural guidance toggle.
        """
        sections = []
        all_blocks = self._load_cached_blocks(page_id) or []

        # 1) Toggle-based activities
        for toggle in self.find_activity_toggle_blocks(page_id):
            try:
                if self._is_block_in_synced_content(toggle, all_blocks):
                    continue
                label = self._extract_plain_text_from_block(toggle) or 'Activity'
                content_text = label
                for child in self.get_toggle_children(toggle['id'])[:20]:
                    content_text += "\n" + (self._extract_plain_text_from_block(child) or '')
                if len(content_text.strip()) >= 20:
                    sections.append({
                        'container_id': toggle['id'],
                        'label': label.strip(),
                        'content_text': content_text.strip()
                    })
            except Exception:
                continue

        # 2) Heading-based activities
        activity_headings = self.find_activity_heading_blocks(page_id)
        id_to_index = {b['id']: i for i, b in enumerate(all_blocks) if b.get('id')}
        for heading in activity_headings:
            try:
                if self._is_block_in_synced_content(heading, all_blocks):
                    continue
                start_idx = id_to_index.get(heading['id'])
                if start_idx is None:
                    continue
                start_level = self._heading_level_from_type(heading.get('type', ''))
                label = self._extract_plain_text_from_block(heading) or 'Activity'
                content_lines = [label]
                # Collect following blocks until next heading of same or higher level
                for j in range(start_idx + 1, min(len(all_blocks), start_idx + 60)):
                    b = all_blocks[j]
                    btype = b.get('type', '')
                    if btype.startswith('heading_'):
                        level = self._heading_level_from_type(btype)
                        if level <= start_level:
                            break
                    # stop at child_page boundaries
                    if btype in ['child_page', 'child_database']:
                        break
                    content_lines.append(self._extract_plain_text_from_block(b) or '')
                content_text = "\n".join([ln for ln in content_lines if ln]).strip()
                if len(content_text) >= 20:
                    sections.append({
                        'container_id': heading['id'],
                        'label': label.strip(),
                        'content_text': content_text
                    })
            except Exception:
                continue

        logging.info(f"🎯 Built {len(sections)} activity sections for cultural guidance")
        return sections

    def find_synced_blocks(self, page_id):
        """
        Find all synced blocks on a page
        
        Args:
            page_id (str): The Notion page ID
            
        Returns:
            list: List of synced block dictionaries with metadata
        """
        try:
            all_blocks = self._get_blocks_efficiently(page_id)
            synced_blocks = []
            
            for block in all_blocks:
                if block.get('type') == 'synced_block':
                    synced_data = block.get('synced_block', {})
                    synced_from = synced_data.get('synced_from')
                    
                    synced_blocks.append({
                        'id': block['id'],
                        'type': 'synced_block',
                        'block_data': block,
                        'is_original': synced_from is None,
                        'synced_from_id': synced_from.get('block_id') if synced_from else None,
                        'has_children': block.get('has_children', False)
                    })
            
            logging.info(f"🔗 Found {len(synced_blocks)} synced blocks on page")
            return synced_blocks
            
        except Exception as e:
            logging.error(f"❌ Error finding synced blocks: {e}")
            return []

    def extract_synced_block_content(self, block_id, synced_block_meta=None):
        """
        Extract all content from a synced block before deletion
        
        Args:
            block_id (str): The synced block ID
            synced_block_meta (dict): Metadata about the synced block (from find_synced_blocks)
            
        Returns:
            list: List of child block data
        """
        try:
            # Get the synced block data to understand its structure
            block_data = self.client.blocks.retrieve(block_id)
            synced_data = block_data.get('synced_block', {})
            synced_from = synced_data.get('synced_from')
            
            # Determine the source of content
            content_source_id = block_id
            if synced_from is not None:
                # This is a reference block - get content from original
                original_block_id = synced_from.get('block_id')
                if original_block_id:
                    logging.info(f"🔄 Reference block {block_id[:8]}... getting content from original {original_block_id[:8]}...")
                    content_source_id = original_block_id
                else:
                    logging.warning(f"⚠️ Reference block {block_id[:8]}... has no valid original block reference")
                    return []
            else:
                logging.info(f"📋 Original block {block_id[:8]}... extracting content directly")
            
            # Extract content from the appropriate source with error handling
            try:
                response = self.client.blocks.children.list(content_source_id)
                children = response.get('results', [])
            except Exception as content_error:
                if "Could not find block" in str(content_error) or "404" in str(content_error):
                    if synced_from is not None:
                        logging.warning(f"🚫 Original block {content_source_id[:8]}... no longer exists (orphaned reference)")
                        logging.info(f"💡 Reference block {block_id[:8]}... will be deleted without content recreation")
                        return []  # Return empty - block will be deleted but not recreated
                    else:
                        logging.error(f"❌ Original block {block_id[:8]}... not found: {content_error}")
                        raise content_error
                else:
                    raise content_error
            
            # Get all children recursively
            all_children = []
            for child in children:
                all_children.append(child)
                if child.get('has_children'):
                    grandchildren = self._extract_block_children_recursively(child['id'])
                    all_children.extend(grandchildren)
            
            logging.info(f"📋 Extracted {len(all_children)} blocks from synced block {block_id[:8]}... (source: {content_source_id[:8]}...)")
            return all_children
            
        except Exception as e:
            logging.error(f"❌ Error extracting synced block content: {e}")
            return []

    def _extract_block_children_recursively(self, block_id):
        """Helper method to recursively extract children from any block"""
        try:
            response = self.client.blocks.children.list(block_id)
            children = response.get('results', [])
            
            all_children = []
            for child in children:
                all_children.append(child)
                if child.get('has_children'):
                    grandchildren = self._extract_block_children_recursively(child['id'])
                    all_children.extend(grandchildren)
            
            return all_children
            
        except Exception as e:
            logging.warning(f"⚠️ Could not extract children from block {block_id[:8]}...: {e}")
            return []

    def unsync_blocks_on_page(self, page_id, dry_run=False):
        """
        Convert all synced blocks on a page to regular blocks
        
        Args:
            page_id (str): The Notion page ID
            dry_run (bool): If True, only show what would be done
            
        Returns:
            dict: Results of the unsync operation
        """
        try:
            synced_blocks = self.find_synced_blocks(page_id)
            
            if not synced_blocks:
                logging.info("✅ No synced blocks found on page")
                return {'success': True, 'blocks_unsynced': 0, 'message': 'No synced blocks to unsync'}
            
            if dry_run:
                logging.info(f"🌀 DRY RUN: Would unsync {len(synced_blocks)} blocks:")
                for block in synced_blocks:
                    block_type = "original" if block['is_original'] else "reference"
                    logging.info(f"   - {block['id'][:8]}... ({block_type})")
                return {'success': True, 'blocks_found': len(synced_blocks), 'dry_run': True}
            
            # Ask for confirmation
            logging.info(f"🔗 Found {len(synced_blocks)} synced blocks to unsync")
            print(f"\n❓ Do you want to proceed with unsyncing {len(synced_blocks)} blocks? (y/N): ", end="")
            response = input().strip().lower()
            
            if response != 'y':
                logging.info("❌ Operation cancelled by user")
                return {'success': False, 'cancelled': True}
            
            return self.convert_synced_to_regular_blocks(synced_blocks)
            
        except Exception as e:
            logging.error(f"❌ Error during unsync operation: {e}")
            return {'success': False, 'error': str(e)}

    def convert_synced_to_regular_blocks(self, synced_blocks):
        """
        Convert synced blocks to regular blocks by delete and recreate
        Properly handles original vs reference synced blocks
        
        Args:
            synced_blocks (list): List of synced block metadata
            
        Returns:
            dict: Results of the conversion
        """
        try:
            unsynced_count = 0
            errors = []
            processed_originals = set()  # Track processed original blocks to avoid duplication
            
            # Create backup directory
            backup_dir = Path("synced_block_backups")
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Group blocks by original vs reference for better processing
            original_blocks = [b for b in synced_blocks if b['is_original']]
            reference_blocks = [b for b in synced_blocks if not b['is_original']]
            
            logging.info(f"📊 Processing {len(original_blocks)} original blocks and {len(reference_blocks)} reference blocks")
            
            # Process all blocks (originals first, then references)
            all_blocks_ordered = original_blocks + reference_blocks
            
            for block_meta in all_blocks_ordered:
                block_id = block_meta['id']
                is_original = block_meta['is_original']
                
                try:
                    # Backup the original block structure
                    backup_file = backup_dir / f"synced_block_{block_id[:8]}_{timestamp}.json"
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        json.dump(block_meta, f, indent=2)  # Save full metadata, not just block_data
                    
                    # Validate content can be extracted before deletion
                    children_content = self.extract_synced_block_content(block_id, block_meta)
                    
                    # For reference blocks, check if we already processed the original
                    if not is_original:
                        original_id = block_meta['synced_from_id']
                        if original_id in processed_originals:
                            logging.info(f"🔄 Reference block {block_id[:8]}... content already extracted from original {original_id[:8]}...")
                    
                    # Get parent information for recreation
                    block_data = self.client.blocks.retrieve(block_id)
                    parent = block_data.get('parent', {})
                    parent_id = parent.get('block_id') or parent.get('page_id')
                    
                    if not parent_id:
                        logging.warning(f"⚠️ Cannot unsync {block_id[:8]}... - no parent found")
                        continue
                    
                    # Handle different scenarios based on content availability
                    if len(children_content) == 0:
                        if is_original:
                            logging.info(f"⚠️ Original block {block_id[:8]}... appears to be empty")
                            proceed = True  # Delete empty original blocks
                        else:
                            # Reference block with no content (likely orphaned)
                            logging.info(f"🚫 Reference block {block_id[:8]}... has no accessible content (orphaned)")
                            proceed = True  # Delete orphaned reference blocks
                    else:
                        proceed = True
                    
                    if not proceed:
                        logging.info(f"⏭️ Skipping {block_id[:8]}... due to processing decision")
                        continue
                    
                    # Delete the synced block
                    self.client.blocks.delete(block_id)
                    logging.info(f"🗑️ Deleted synced block {block_id[:8]}... ({'original' if is_original else 'reference'})")
                    
                    # Recreate content as regular blocks
                    if children_content:
                        # Create appropriate container based on content
                        if len(children_content) == 1:
                            # Single child - recreate directly
                            result = self.client.blocks.children.append(parent_id, children=children_content)
                        else:
                            # Multiple children - wrap in toggle for organization
                            container_block = {
                                "object": "block",
                                "type": "toggle", 
                                "toggle": {
                                    "rich_text": [{
                                        "type": "text",
                                        "text": {"content": f"Content from synced block ({'original' if is_original else 'reference'})"}
                                    }],
                                    "children": children_content[:40]  # Limit children to prevent API errors
                                }
                            }
                            result = self.client.blocks.children.append(parent_id, children=[container_block])
                        
                        if result:
                            logging.info(f"✅ Recreated {len(children_content)} blocks for {block_id[:8]}... as regular content")
                            unsynced_count += 1
                    else:
                        # No content to recreate
                        if is_original:
                            logging.info(f"🗑️ Deleted empty original synced block {block_id[:8]}...")
                        else:
                            logging.info(f"🧹 Cleaned up orphaned reference block {block_id[:8]}...")
                        unsynced_count += 1
                    
                    # Track processed originals
                    if is_original:
                        processed_originals.add(block_id)
                        
                except Exception as e:
                    error_msg = f"Failed to unsync {block_id[:8]}...: {e}"
                    logging.error(f"❌ {error_msg}")
                    errors.append(error_msg)
            
            success_msg = f"Unsynced {unsynced_count} blocks"
            if errors:
                success_msg += f" with {len(errors)} errors"
            
            return {
                'success': unsynced_count > 0,
                'blocks_unsynced': unsynced_count,
                'errors': errors,
                'message': success_msg
            }
            
        except Exception as e:
            logging.error(f"❌ Error converting synced blocks: {e}")
            return {'success': False, 'error': str(e)}

    def append_cultural_toggle_to_container(self, container_block_id: str, title: str, markdown_content: str, max_blocks: int = 40):
        """Append a toggle titled `title` with parsed markdown content as children under the container block."""
        try:
            # Check if container is accessible (not archived/deleted)
            if not self._is_block_accessible(container_block_id):
                logging.warning(f"🚫 SKIP: Container {container_block_id[:8]}... is archived or deleted")
                return {'success': True, 'skipped': True, 'reason': 'archived_or_deleted'}
                
            # Guard synced ancestry
            if self._is_block_or_ancestor_synced_api(container_block_id):
                logging.warning(f"🚫 PROTECTED: Skipping cultural toggle under synced content {container_block_id[:8]}...")
                return {'success': True, 'skipped': True, 'reason': 'synced_content'}
                
            # Idempotency: skip if exists
            title_prefix = title.split(':')[0].strip() if ':' in title else title
            if self._child_toggle_exists(container_block_id, title_prefix):
                logging.info("♻️ Cultural toggle already exists; skipping")
                return {'success': True, 'skipped': True, 'reason': 'already_exists'}

            # Build structured children if possible
            children_blocks = self.build_cultural_guidance_children(markdown_content)[:max_blocks]
            
            # Handle table blocks that need special creation
            processed_children = []
            for child_block in children_blocks:
                if child_block.get("_create_table_with_rows"):
                    # Skip table blocks for now - they need special handling
                    # TODO: Implement proper table creation after toggle is created
                    continue
                else:
                    processed_children.append(child_block)
            
            toggle_block = self.create_toggle_block(title, processed_children)
            try:
                result = self.client.blocks.children.append(container_block_id, children=[toggle_block])
                
                # Now handle any table blocks that were deferred
                toggle_id = result['results'][0]['id'] if result.get('results') else None
                if toggle_id:
                    for child_block in children_blocks:
                        if child_block.get("_create_table_with_rows"):
                            self._create_table_with_rows(toggle_id, child_block["_create_table_with_rows"])
                
                return {'success': True, 'response': result}
            except Exception as e:
                # Fallback: append to parent of the container
                logging.info(f"↩️ Falling back to append under parent of container: {e}")
                container = self.client.blocks.retrieve(container_block_id)
                parent = container.get('parent') or {}
                target_id = parent.get('block_id') or parent.get('page_id')
                if not target_id:
                    raise
                result = self.client.blocks.children.append(target_id, children=[toggle_block])
                return {'success': True, 'response': result, 'fallback': True}
        except Exception as e:
            logging.error(f"❌ Failed to append cultural toggle: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_toggle_children(self, toggle_block_id):
        """
        Get children of a toggle block
        
        Args:
            toggle_block_id (str): Toggle block ID
            
        Returns:
            list: Child blocks of the toggle
        """
        try:
            response = self.client.blocks.children.list(toggle_block_id)
            children = response.get('results', [])
            logging.info(f"📁 Toggle {toggle_block_id[:8]}... has {len(children)} children")
            return children
        except Exception as e:
            logging.warning(f"⚠️ Could not get toggle children: {e}")
            return []

    def _is_block_accessible(self, block_id: str) -> bool:
        """Check if a block exists and is not archived."""
        try:
            block = self.client.blocks.retrieve(block_id)
            if block.get('archived', False):
                logging.warning(f"📁 Block {block_id[:8]}... is archived")
                return False
            return True
        except Exception as e:
            if "Could not find block" in str(e) or "404" in str(e):
                logging.warning(f"🚫 Block {block_id[:8]}... not found (likely deleted)")
                return False
            logging.warning(f"⚠️ Could not access block {block_id[:8]}...: {e}")
            return False

    def _child_toggle_exists(self, container_block_id: str, title_prefix: str) -> bool:
        """Return True if a child toggle under container starts with title_prefix."""
        try:
            # First check if the container is accessible
            if not self._is_block_accessible(container_block_id):
                logging.warning(f"🚫 Cannot check toggles: container {container_block_id[:8]}... is not accessible")
                return False
                
            resp = self.client.blocks.children.list(container_block_id)
            for child in resp.get('results', []):
                if child.get('type') != 'toggle':
                    continue
                text = self._extract_plain_text_from_block(child) or ''
                if text.strip().startswith(title_prefix):
                    return True
        except Exception as e:
            if "Could not find block" in str(e) or "404" in str(e):
                logging.warning(f"🚫 Container {container_block_id[:8]}... not found (likely deleted)")
            else:
                logging.warning(f"⚠️ Could not check existing toggles: {e}")
        return False

    def _build_section_toggle(self, title: str, items: list) -> dict:
        """Create a toggle titled `title` containing bulleted list items from `items` text list."""
        children = []
        for raw in items:
            text = raw.strip()
            if not text:
                continue
            # remove leading bullet markers if present
            text = re.sub(r"^[-*•]\s+", "", text)
            rich = self._markdown_to_rich_text(text)
            children.append(self.create_bulleted_list_item_block(text, rich_text=rich))
        return self.create_toggle_block(title, children)

    def build_cultural_guidance_children(self, markdown_text: str) -> list:
        """Convert cultural analysis markdown into nested toggles by sections.

        Sections recognized (case-insensitive):
        - Cultural Strengths
        - Cultural Challenges
        - Alternative Activities
        - Targeted Adaptations

        Falls back to flat parsing if no sections found.
        """
        lines = [ln.rstrip() for ln in markdown_text.split('\n')]
        sections = {
            'cultural strengths': [],
            'cultural challenges': [],
            'alternative activities': [],
            'targeted adaptations': []
        }
        current_key = None
        header_patterns = [
            re.compile(r"^##\s*(cultural strengths)\b", re.I),
            re.compile(r"^##\s*(cultural challenges)\b", re.I),
            re.compile(r"^##\s*(alternative activities)\b", re.I),
            re.compile(r"^##\s*(targeted adaptations)\b", re.I),
            # Bold label bullet style: **Cultural Strengths:**
            re.compile(r"^\*?\s*\*\*(cultural strengths)\*\*:?\s*$", re.I),
            re.compile(r"^\*?\s*\*\*(cultural challenges)\*\*:?\s*$", re.I),
            re.compile(r"^\*?\s*\*\*(alternative activities)\*\*:?\s*$", re.I),
            re.compile(r"^\*?\s*\*\*(targeted adaptations)\*\*:?\s*$", re.I),
        ]
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                continue
            found_header = False
            for pat in header_patterns:
                m = pat.match(stripped)
                if m:
                    current_key = m.group(1).lower()
                    found_header = True
                    break
            if found_header:
                continue
            # Collect bullet-like lines under current section
            if current_key and (stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('• ') or re.match(r'^\d+\.\s+', stripped)):
                sections[current_key].append(stripped)

        def strip_leading_bullet(s: str) -> str:
            return re.sub(r"^(?:[-*•]\s+|\d+\.\s+)", "", s).strip()

        def strip_redundant_label_for_section(section_key: str, text: str) -> str:
            # Remove a leading label that duplicates the section, e.g., "Challenges: ..." inside Challenges
            label = section_key.split()[-1]  # strengths/challenges/activities/adaptations
            pattern = re.compile(rf"^\*?\*?{label}\*?\*?:\s+", re.I)
            return pattern.sub("", text)

        def is_topic_header(text: str) -> bool:
            # A line that ends with a colon and has no other content after it (ignoring bold markers)
            tmp = text.strip()
            # Remove surrounding bold markers for detection
            tmp = re.sub(r"^\*\*(.*?)\*\*$", r"\1", tmp)
            return tmp.endswith(':') and len(tmp.rstrip(':').strip()) > 0 and not re.search(r":\s+\S+", tmp)

        def clean_title(text: str) -> str:
            # Remove trailing colon and surrounding bold markers for titles
            t = text.strip()
            t = re.sub(r"^\*\*(.*?)\*\*$", r"\1", t)
            t = t.rstrip(':').strip()
            return t

        # Build toggles for sections that have content, grouping sub-topics
        children = []
        for key, items in sections.items():
            if items:
                title = key.title()
                # Pre-clean items
                cleaned_items = []
                for it in items:
                    content = strip_leading_bullet(it)
                    content = strip_redundant_label_for_section(key, content)
                    cleaned_items.append(content)
                # Group into topic headers and their child bullets
                grouped = []
                idx = 0
                while idx < len(cleaned_items):
                    current = cleaned_items[idx]
                    if is_topic_header(current):
                        topic_title = clean_title(current)
                        group_children = []
                        idx += 1
                        while idx < len(cleaned_items):
                            nxt = cleaned_items[idx]
                            if is_topic_header(nxt):
                                break
                            group_children.append(nxt)
                            idx += 1
                        if group_children:
                            # Create nested toggle for this topic
                            title_rich = self._markdown_to_rich_text(topic_title)
                            topic_toggle = self.create_toggle_block(topic_title, [
                                # children bulleted items
                            ])
                            # Replace title to rich_text
                            topic_toggle['toggle']['rich_text'] = title_rich
                            # Build children bullets
                            topic_children_blocks = []
                            for gc in group_children:
                                rich = self._markdown_to_rich_text(gc)
                                topic_children_blocks.append(self.create_bulleted_list_item_block(gc, rich_text=rich))
                            topic_toggle['toggle']['children'] = topic_children_blocks
                            grouped.append(topic_toggle)
                        else:
                            # No children; render as single bullet
                            rich = self._markdown_to_rich_text(topic_title)
                            grouped.append(self.create_bulleted_list_item_block(topic_title, rich_text=rich))
                    else:
                        # Simple bullet
                        rich = self._markdown_to_rich_text(current)
                        grouped.append(self.create_bulleted_list_item_block(current, rich_text=rich))
                        idx += 1
                # Wrap grouped content under a section toggle
                section_toggle = self.create_toggle_block(title, grouped if grouped else None)
                children.append(section_toggle)

        if children:
            return children
        # Fallback: flat conversion
        parsed_blocks = self.parse_markdown_to_blocks(markdown_text)
        # Handle table blocks that need special processing
        return self._process_special_blocks(parsed_blocks)
    
    def _process_special_blocks(self, blocks):
        """
        Process blocks that need special API handling (like tables)
        
        Args:
            blocks (list): List of parsed blocks
            
        Returns:
            list: Processed blocks with table creation deferred
        """
        processed_blocks = []
        
        for block in blocks:
            if block.get("_needs_special_handling") and block.get("type") == "table":
                # Store table creation info for later processing
                table_rows = block.get("_table_rows", [])
                if table_rows:
                    # Mark block for special table creation
                    table_block = self.create_table_block(
                        len(table_rows[0]) if table_rows else 1, 
                        has_column_header=True
                    )
                    table_block["_create_table_with_rows"] = table_rows
                    processed_blocks.append(table_block)
                else:
                    processed_blocks.append(block)
            else:
                processed_blocks.append(block)
        
        return processed_blocks
    
    def _create_table_with_rows(self, parent_block_id: str, table_rows: list):
        """
        Create a table block with rows using the Notion API
        
        Args:
            parent_block_id (str): Parent block to append table to
            table_rows (list): List of row data (list of cell strings)
        """
        try:
            if not table_rows:
                return
                
            num_columns = len(table_rows[0])
            
            # Create table rows first
            row_blocks = []
            for row_cells in table_rows:
                # Ensure all rows have the same number of columns
                while len(row_cells) < num_columns:
                    row_cells.append("")
                row_blocks.append(self.create_table_row_block(row_cells[:num_columns]))
            
            # Create the table block with all rows included
            table_block = self.create_table_block(num_columns, has_column_header=True, children=row_blocks)
            logging.info(f"🔍 Creating table block with {len(row_blocks)} rows")
            result = self.client.blocks.children.append(parent_block_id, children=[table_block])
            logging.info(f"✅ Created table with {len(row_blocks)} rows")
                
        except Exception as e:
            logging.error(f"❌ Failed to create table: {e}")
    
    def find_activity_blocks(self, page_id):
        """
        Find blocks that represent activities (improved detection)
        
        Args:
            page_id (str): The Notion page ID
            
        Returns:
            list: List of blocks that appear to be activities
        """
        all_activities = []
        
        # First, find activity toggle blocks and their children
        activity_toggles = self.find_activity_toggle_blocks(page_id)
        
        for toggle in activity_toggles:
            # Add the toggle itself
            all_activities.append(toggle)
            
            # Add its children (these are the actual activities)
            children = self.get_toggle_children(toggle['id'])
            all_activities.extend(children)
        
        # Also find standalone activity blocks
        def is_standalone_activity_block(block):
            block_type = block.get('type')
            text_content = self._extract_plain_text_from_block(block)
            
            if not text_content:
                return False
            
            text_lower = text_content.lower()
            # Look for activity indicators
            activity_indicators = [
                'activity', 'exercise', 'discussion', 'group work', 
                'practice', 'role play', 'simulation', 'workshop',
                'introduction activity', 'discovery activity',
                'minutes', 'debrief', 'see:', 'do:', 'equip:',
                '👀', '🕺', '🎓',  # See, Do, Equip emojis
                '🕰', '🗿', '🔬'  # Time, notes, microscope emojis
            ]
            
            return any(indicator in text_lower for indicator in activity_indicators)
        
        standalone_activities = self.find_blocks_by_criteria(page_id, is_standalone_activity_block)
        all_activities.extend(standalone_activities)
        
        # Remove duplicates
        unique_activities = []
        seen_ids = set()
        for activity in all_activities:
            if activity['id'] not in seen_ids:
                unique_activities.append(activity)
                seen_ids.add(activity['id'])
        
        logging.info(f"🎯 Found {len(unique_activities)} total activity blocks")
        return unique_activities
    
    def insert_trainer_questions_section(self, page_id, questions_markdown):
        """
        Insert a "Trainer Evaluation Questions" section with the provided questions
        Tries to place after "Conclusion" and before "Course Materials", otherwise at the end
        
        Args:
            page_id (str): The Notion page ID
            questions_markdown (str): Markdown text containing the questions
            
        Returns:
            dict: Results of the insertion operation
        """
        try:
            # Create the section blocks
            section_blocks = [
                self.create_heading_block("Trainer Evaluation Questions", 2)
            ]
            
            # Parse questions and add them
            question_blocks = self.parse_markdown_to_blocks(questions_markdown)
            section_blocks.extend(question_blocks)
            
            # Try to find the optimal insertion point
            insertion_point = self._find_trainer_questions_insertion_point(page_id)
            
            if insertion_point:
                # Insert at the specific location
                return self.insert_blocks_at_position(page_id, section_blocks, insertion_point)
            else:
                # Fallback to appending at the end
                logging.info("📍 No ideal insertion point found, adding trainer questions at end of document")
                return self.append_blocks_to_page(page_id, section_blocks)
            
        except Exception as e:
            logging.error(f"❌ Error inserting trainer questions: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_added': 0
            }
    
    def _find_trainer_questions_insertion_point(self, page_id):
        """
        Find the best insertion point for trainer questions:
        1. After "Conclusion" heading
        2. Before "Course Materials" heading
        3. Return None if neither is found (will append at end)
        
        Args:
            page_id (str): The Notion page ID
            
        Returns:
            str: Block ID to insert after, or None
        """
        try:
            # Get all blocks from the page
            all_blocks = self.get_all_page_blocks(page_id)
            
            conclusion_block_id = None
            course_materials_block_id = None
            
            # Look for end-section headings (expanded list)
            conclusion_keywords = ['conclusion', 'summary', 'wrap', 'wrap up', 'wrap-up', 'next steps', 'review', 'closing']
            materials_keywords = ['course materials', 'course material', 'resources', 'handouts', 'materials', 'appendix', 'references']
            
            for block in all_blocks:
                if block.get('type') == 'heading_1' or block.get('type') == 'heading_2' or block.get('type') == 'heading_3':
                    heading_text = self.extract_plain_text_from_rich_text(
                        block.get(block['type'], {}).get('rich_text', [])
                    ).lower()
                    
                    # Check for conclusion-type headings
                    for keyword in conclusion_keywords:
                        if keyword in heading_text:
                            conclusion_block_id = block['id']
                            logging.info(f"📍 Found conclusion-type heading '{heading_text}' at block {conclusion_block_id}")
                            break
                    
                    # Check for materials-type headings  
                    for keyword in materials_keywords:
                        if keyword in heading_text:
                            course_materials_block_id = block['id']
                            logging.info(f"📍 Found materials-type heading '{heading_text}' at block {course_materials_block_id}")
                            break
            
            # Determine insertion point based on what we found
            if conclusion_block_id and course_materials_block_id:
                # Find the last block after conclusion but before course materials
                insert_after_id = self._find_last_block_before_target(all_blocks, conclusion_block_id, course_materials_block_id)
                if insert_after_id:
                    logging.info(f"📍 Will insert trainer questions after conclusion and before course materials (after block {insert_after_id})")
                    return insert_after_id
            
            if conclusion_block_id:
                # Find the last block in the conclusion section
                insert_after_id = self._find_last_block_in_section(all_blocks, conclusion_block_id)
                if insert_after_id:
                    logging.info(f"📍 Will insert trainer questions after conclusion section (after block {insert_after_id})")
                    return insert_after_id
            
            if course_materials_block_id:
                # Insert just before course materials
                insert_before_index = next((i for i, block in enumerate(all_blocks) if block['id'] == course_materials_block_id), None)
                if insert_before_index and insert_before_index > 0:
                    insert_after_id = all_blocks[insert_before_index - 1]['id']
                    logging.info(f"📍 Will insert trainer questions before course materials (after block {insert_after_id})")
                    return insert_after_id
            
            logging.info("📍 No end-section headings found, using 90% position fallback")
            
            # Fallback: insert at 90% through the document instead of the very end
            if all_blocks:
                insertion_position = int(len(all_blocks) * 0.9)
                if insertion_position > 0 and insertion_position < len(all_blocks):
                    fallback_insert_after_id = all_blocks[insertion_position - 1]['id']
                    logging.info(f"📍 Will insert trainer questions at 90% position (after block {fallback_insert_after_id})")
                    return fallback_insert_after_id
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Error finding insertion point: {e}")
            return None
    
    def _find_last_block_before_target(self, all_blocks, start_block_id, target_block_id):
        """Find the last block after start_block_id but before target_block_id"""
        try:
            start_index = next((i for i, block in enumerate(all_blocks) if block['id'] == start_block_id), None)
            target_index = next((i for i, block in enumerate(all_blocks) if block['id'] == target_block_id), None)
            
            if start_index is not None and target_index is not None and target_index > start_index:
                # Return the block just before the target
                return all_blocks[target_index - 1]['id']
            return None
        except Exception:
            return None
    
    def _find_last_block_in_section(self, all_blocks, heading_block_id):
        """Find the last block in a section defined by a heading"""
        try:
            heading_index = next((i for i, block in enumerate(all_blocks) if block['id'] == heading_block_id), None)
            if heading_index is None:
                return None
            
            # Look for the next heading or end of document
            for i in range(heading_index + 1, len(all_blocks)):
                block = all_blocks[i]
                if block.get('type') in ['heading_1', 'heading_2']:
                    # Found next heading, return the previous block
                    return all_blocks[i - 1]['id']
            
            # No next heading found, return the last block
            if len(all_blocks) > heading_index + 1:
                return all_blocks[-1]['id']
            
            return heading_block_id  # Only the heading exists
        except Exception:
            return None
    
    def insert_blocks_at_position(self, page_id, blocks_to_insert, insert_after_block_id):
        """
        Insert blocks at a specific position in the page (after the specified block)
        
        Args:
            page_id (str): The Notion page ID
            blocks_to_insert (list): List of block objects to insert
            insert_after_block_id (str): Block ID to insert after
            
        Returns:
            dict: Results of the insertion operation
        """
        try:
            # Use Notion's API to insert blocks after the specified block
            response = self.client.blocks.children.append(
                block_id=insert_after_block_id,
                children=blocks_to_insert
            )
            
            logging.info(f"✅ Successfully inserted {len(blocks_to_insert)} blocks after {insert_after_block_id}")
            
            return {
                'success': True,
                'blocks_added': len(blocks_to_insert),
                'inserted_after': insert_after_block_id,
                'response': response
            }
            
        except Exception as e:
            logging.error(f"❌ Error inserting blocks at position: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_added': 0
            }
    
    def insert_cultural_adaptations_after_activities(self, page_id, cultural_analysis):
        """
        Insert "Cultural Adaptations" toggle blocks after each identified activity
        
        Args:
            page_id (str): The Notion page ID
            cultural_analysis (str): The cultural analysis content
            
        Returns:
            dict: Results of the insertion operation
        """
        try:
            # Find activity blocks
            activity_blocks = self.find_activity_blocks(page_id)
            
            if not activity_blocks:
                logging.warning("⚠️ No activity blocks found for cultural adaptations")
                return {
                    'success': False,
                    'message': 'No activity blocks found',
                    'blocks_added': 0
                }
            
            # For now, we'll add a single cultural adaptations section at the end
            # since Notion API doesn't support inserting at specific positions easily
            
            # Parse cultural analysis and limit blocks to avoid API limits
            cultural_content_blocks = self.parse_markdown_to_blocks(cultural_analysis)
            
            # Notion API limit: toggles can only have 100 children, so split if needed
            if len(cultural_content_blocks) > 90:  # Keep some buffer
                # Just add the heading and a summary paragraph instead
                cultural_blocks = [
                    self.create_heading_block("Cultural Adaptations", 2),
                    self.create_paragraph_block("Cultural analysis generated. See full analysis in saved files.")
                ]
            else:
                cultural_blocks = [
                    self.create_heading_block("Cultural Adaptations", 2),
                    self.create_toggle_block(
                        "Cultural Considerations for Activities",
                        cultural_content_blocks[:90]  # Limit to 90 blocks
                    )
                ]
            
            return self.append_blocks_to_page(page_id, cultural_blocks)
            
        except Exception as e:
            logging.error(f"❌ Error inserting cultural adaptations: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_added': 0
            }
    
    def update_specific_blocks_with_enhanced_content(self, page_id, enhanced_markdown):
        """
        Update specific blocks with enhanced content (safer approach)
        
        Args:
            page_id (str): The Notion page ID
            enhanced_markdown (str): Enhanced markdown content
            
        Returns:
            dict: Results of the update operation
        """
        try:
            # Get all current blocks
            all_blocks = self._load_cached_blocks(page_id)
            
            if not all_blocks:
                return {
                    'success': False,
                    'message': 'No cached blocks found',
                    'blocks_updated': 0
                }
            
            # Parse enhanced content into sections
            enhanced_lines = enhanced_markdown.split('\n')
            enhanced_sections = []
            current_section = []
            
            for line in enhanced_lines:
                if line.strip().startswith('#') and current_section:
                    enhanced_sections.append('\n'.join(current_section))
                    current_section = [line]
                else:
                    current_section.append(line)
            
            if current_section:
                enhanced_sections.append('\n'.join(current_section))
            
            # Find updatable text blocks and update them with enhanced content
            # SKIP synced blocks to avoid modifying shared content
            updatable_blocks = []
            for block in all_blocks:
                block_type = block.get('type')
                
                # Skip synced blocks - these are shared content that shouldn't be modified
                if block_type == 'synced_block':
                    continue
                    
                if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                                'bulleted_list_item', 'numbered_list_item']:
                    text_content = self._extract_plain_text_from_block(block)
                    if text_content and len(text_content.strip()) > 10:  # Only meaningful content
                        updatable_blocks.append(block)
            
            updated_count = 0
            # Update blocks with enhanced content (match by position/similarity)
            for i, block in enumerate(updatable_blocks[:min(len(enhanced_sections), 20)]):  # Limit updates
                try:
                    if i < len(enhanced_sections):
                        enhanced_section = enhanced_sections[i].strip()
                        if enhanced_section:
                            # Extract just the text part (remove markdown formatting)
                            enhanced_text = enhanced_section
                            # Remove markdown headers
                            enhanced_text = re.sub(r'^#+\s*', '', enhanced_text)
                            # Remove bullet points
                            enhanced_text = re.sub(r'^[\-\*]\s*', '', enhanced_text)
                            
                            if enhanced_text.strip():
                                # Trim text to fit Notion's 2000 character limit
                                trimmed_text = enhanced_text.strip()[:1900]  # Leave buffer for safety
                                if len(enhanced_text.strip()) > 1900:
                                    trimmed_text += "..."
                                
                                # Get original text for structure preservation
                                original_text = self._extract_plain_text_from_block(block)
                                
                                # Use structure-preserving update
                                self.update_block_text_preserving_structure(block['id'], trimmed_text, original_text)
                                updated_count += 1
                                logging.info(f"📝 Updated block with enhanced content (preserving structure)")
                except Exception as e:
                    logging.warning(f"⚠️ Could not update block {block['id']}: {e}")
            
            return {
                'success': True,
                'blocks_updated': updated_count,
                'message': f"Updated {updated_count} blocks with enhanced reading content"
            }
            
        except Exception as e:
            logging.error(f"❌ Error updating blocks with enhanced content: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_updated': 0
            }
    
    def _get_blocks_efficiently(self, page_id, block_limit=None):
        """
        Get blocks efficiently - use cached if available, otherwise fetch only what we need
        
        Args:
            page_id (str): Notion page ID
            block_limit (int): Optional limit on number of blocks needed
            
        Returns:
            list: List of blocks
        """
        # Try cached data first
        all_blocks = self._load_cached_blocks(page_id)
        
        if all_blocks is not None:
            logging.info("🗂️ Using cached block data (much faster!)")
            return all_blocks
            
        # No cached data - need to fetch from API
        if block_limit and block_limit <= 20:
            # For small requests, fetch only top-level blocks + limited children
            logging.info(f"📡 Fetching limited blocks from API (limit: {block_limit})")
            return self._get_limited_blocks(page_id, block_limit)
        else:
            # For large requests or no limit, fall back to full recursive fetch
            logging.info("📡 No cached data available, falling back to full API fetch...")
            return self._get_all_blocks_recursively(page_id)
    
    def get_all_page_blocks(self, page_id):
        """
        Get all blocks from a page - wrapper around _get_blocks_efficiently
        
        Args:
            page_id (str): Notion page ID
            
        Returns:
            list: All blocks from the page
        """
        return self._get_blocks_efficiently(page_id)
    
    def _get_limited_blocks(self, page_id, limit):
        """
        Fetch a limited number of blocks without full recursive scan
        
        Args:
            page_id (str): Notion page ID  
            limit (int): Maximum number of blocks to fetch
            
        Returns:
            list: Limited list of blocks
        """
        try:
            # Get top-level blocks with pagination
            blocks = []
            start_cursor = None
            
            while len(blocks) < limit:
                response = self.client.blocks.children.list(
                    block_id=page_id,
                    start_cursor=start_cursor,
                    page_size=min(limit - len(blocks), 100)  # Don't fetch more than needed
                )
                
                for block in response.get('results', []):
                    blocks.append(block)
                    if len(blocks) >= limit:
                        break
                
                # Check if there are more pages
                if not response.get('has_more', False):
                    break
                    
                start_cursor = response.get('next_cursor')
                
                if len(blocks) >= limit:
                    break
            
            logging.info(f"📡 Fetched {len(blocks)} blocks from API (limited fetch)")
            return blocks
            
        except Exception as e:
            logging.error(f"❌ Error fetching limited blocks: {e}")
            return []


    def intelligent_block_by_block_update(self, page_id, enhancement_prompt, ai_handler, block_limit=None):
        """
        Update blocks one by one using AI for each block intelligently
        
        Args:
            page_id (str): Notion page ID
            enhancement_prompt (str): What enhancement to apply
            ai_handler: AI handler for real-time assistance
            block_limit (int): Optional limit on number of blocks to process
            
        Returns:
            dict: Results of intelligent updates
        """
        try:
            # Get blocks efficiently based on our needs
            all_blocks = self._get_blocks_efficiently(page_id, block_limit)
            
            if not all_blocks:
                return {
                    'success': False,
                    'message': 'No blocks found',
                    'blocks_updated': 0
                }
            
            # Find updatable blocks (STRICT synced block protection!)
            updatable_blocks = []
            synced_blocks_found = 0
            
            for block in all_blocks:
                block_type = block.get('type')
                block_id = block.get('id', 'unknown')
                
                # CRITICAL: Skip synced blocks - these are shared content!
                if block_type == 'synced_block':
                    synced_blocks_found += 1
                    logging.warning(f"🚫 PROTECTED: Skipping synced block {block_id[:8]}... (shared content)")
                    continue
                
                # Skip other problematic types (keep media to edit captions)
                if block_type in ['child_page', 'child_database', 'embed']:
                    logging.info(f"⏭️ Skipping {block_type} block {block_id[:8]}...")
                    continue
                
                # Check if block is inside a synced block (parent check)
                if self._is_block_in_synced_content(block, all_blocks):
                    logging.warning(f"🚫 PROTECTED: Skipping block {block_id[:8]}... (inside synced content)")
                    continue
                    
                if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                                  'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'toggle', 'to_do',
                                  'image', 'video', 'file', 'pdf', 'audio', 'bookmark']:
                    text_content = self._extract_plain_text_from_block(block)
                    if text_content and len(text_content.strip()) > 5:
                        updatable_blocks.append(block)
                        # Apply block limit during initial filtering (synced blocks don't count)
                        if block_limit and block_limit > 0 and len(updatable_blocks) >= block_limit:
                            logging.info(f"🔢 Block limit reached: {block_limit} processable blocks found")
                            break
            
            logging.info(f"🚫 Protected {synced_blocks_found} synced blocks from modification")
            logging.info(f"📝 Found {len(updatable_blocks)} updatable blocks (excluding protected content)")
            
            # Also find and process toggle children (if we haven't reached the limit)
            if not block_limit or len(updatable_blocks) < block_limit:
                toggle_children = self._find_toggle_children_blocks(page_id)
                logging.info(f"🔄 Found {len(toggle_children)} additional blocks inside toggles")
                
                # Add toggle children to updatable blocks (if not already included)
                for toggle_child in toggle_children:
                    # Check if we've reached the block limit
                    if block_limit and block_limit > 0 and len(updatable_blocks) >= block_limit:
                        logging.info(f"🔢 Block limit reached during toggle processing: {block_limit} blocks")
                        break
                        
                    if not any(b['id'] == toggle_child['id'] for b in updatable_blocks):
                        if not self._is_block_in_synced_content(toggle_child, all_blocks):
                            tc_type = toggle_child.get('type')
                            if tc_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                                           'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'toggle', 'to_do',
                                           'image', 'video', 'file', 'pdf', 'audio', 'bookmark']:
                                updatable_blocks.append(toggle_child)
            
            logging.info(f"🤖 Starting intelligent block-by-block update on {len(updatable_blocks)} total blocks (including toggle children)")
            
            successful_updates = 0
            skipped_updates = 0
            failed_updates = 0
            
            if block_limit and block_limit > 0:
                logging.info(f"🔢 Block limit applied: processing {len(updatable_blocks)} blocks (limit: {block_limit}, {synced_blocks_found} synced blocks skipped)")
            
            # Process blocks one by one with AI (no hard cap; gentle rate limiting)
            # Track context from previous blocks
            block_context = []
            
            for i, block in enumerate(updatable_blocks):
                try:
                    logging.info(f"🔄 Processing block {i+1}/{len(updatable_blocks)}: {block.get('type')}")
                    
                    result = self.intelligent_block_update_with_context(
                        block['id'], 
                        enhancement_prompt, 
                        ai_handler,
                        block_context
                    )
                    
                    if result['success']:
                        if result.get('skipped'):
                            skipped_updates += 1
                            logging.info(f"⏭️ Skipped block: {result.get('reason', 'Unknown')}")
                        else:
                            successful_updates += 1
                            logging.info(f"✅ Enhanced block successfully")
                            
                            # Add to context if successfully processed
                            original_text = self._extract_plain_text_from_block(block)
                            enhanced_text = result.get('enhanced_text', '')
                            if original_text and enhanced_text:
                                block_context.append({
                                    'original': original_text,
                                    'enhanced': enhanced_text,
                                    'type': block.get('type')
                                })
                                
                                # Keep only last 3-5 blocks for context (avoid token bloat)
                                if len(block_context) > 5:
                                    block_context = block_context[-5:]
                    else:
                        failed_updates += 1
                        logging.warning(f"❌ Block update failed: {result.get('error', 'Unknown')}")
                        
                    # Gentle rate limit to respect API
                    time.sleep(0.2)
                except Exception as e:
                    failed_updates += 1
                    logging.error(f"❌ Error processing block {i+1}: {e}")
            
            return {
                'success': successful_updates > 0,
                'blocks_processed': len(updatable_blocks),
                'successful_updates': successful_updates,
                'skipped_updates': skipped_updates,
                'failed_updates': failed_updates,
                'message': f"Processed {len(updatable_blocks)} blocks: {successful_updates} updated, {skipped_updates} skipped, {failed_updates} failed"
            }
            
        except Exception as e:
            logging.error(f"❌ Intelligent block update failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_updated': 0
            }
    
    def intelligent_block_update_with_context(self, block_id, enhancement_prompt, ai_handler, block_context=None):
        """
        Use AI to intelligently update a single block with context from previous blocks
        
        Args:
            block_id (str): Block ID to update
            enhancement_prompt (str): What kind of enhancement to apply
            ai_handler: AI handler for real-time assistance
            block_context (list): Previous blocks context for smarter decisions
            
        Returns:
            dict: Update results including enhanced_text for context tracking
        """
        try:
            # Get current block with full structure
            current_block = self.client.blocks.retrieve(block_id)
            block_type = current_block.get('type')

            # HARD GUARD: never modify synced blocks or their children
            if block_type == 'synced_block' or self._is_block_or_ancestor_synced_api(block_id):
                return {'success': True, 'skipped': True, 'reason': 'Synced content'}

            # Extract current rich text structure
            rich_text_array = self._get_rich_text_from_block(current_block, block_type)
            
            if not rich_text_array:
                return {'success': False, 'error': 'No rich text content'}
            
            # Extract formatting information to preserve
            formatting_info = self._extract_emoji_and_formatting_info(rich_text_array)
            
            # Convert rich text to plain text for AI
            current_plain_text = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text_array])
            
            # For context-aware processing, consider even very short text
            if len(current_plain_text.strip()) < 2:
                return {'success': True, 'skipped': True, 'reason': 'Empty content'}
            
            # Build context-aware AI prompt using unified prompt system
            context_info = ""
            if block_context:
                context_info = "\n\nRECENT BLOCKS CONTEXT (for understanding pattern and making intelligent decisions):\n"
                for i, ctx in enumerate(block_context[-3:]):  # Last 3 blocks
                    context_info += f"{i+1}. [{ctx['type']}] '{ctx['original']}' → '{ctx['enhanced']}'\n"
                context_info += "\nNow process this block considering the above context:\n"
            
            # Create basic formatting context (backwards compatibility)
            formatting_context = ""
            if formatting_info.get('leading_emoji'):
                formatting_context += f"\n- PRESERVE EMOJI: Start with '{formatting_info['leading_emoji']}' "
            if formatting_info.get('has_italic'):
                formatting_context += "\n- The original has italic text - maintain emphasis where appropriate"
            if formatting_info.get('has_bold'):
                formatting_context += "\n- The original has bold text - maintain strong emphasis where appropriate"
            
            # Generate detailed formatting description
            detailed_formatting = self._build_detailed_formatting_description(formatting_info)
            
            # Detect if this is a translation task
            is_translation = enhancement_prompt.startswith("translate_to_")
            target_language = enhancement_prompt.replace("translate_to_", "") if is_translation else None
            
            # Load appropriate prompt from prompts.txt
            prompt_name = "Translation" if is_translation else "Reading"
            prompt_template = load_prompt_from_file(prompt_name)
            
            if prompt_template:
                # Use unified prompt system with comprehensive formatting details
                format_params = {
                    'context_info': context_info,
                    'block_type': block_type,
                    'current_plain_text': current_plain_text,
                    'detailed_formatting': detailed_formatting
                }
                
                # Add target_language for translation prompts
                if is_translation and target_language:
                    format_params['target_language'] = target_language
                
                ai_prompt = prompt_template.format(**format_params)
            else:
                # Fallback to basic prompt if file loading fails
                ai_prompt = f"""
 You are improving Notion content while preserving meaning and visual elements.{context_info}
 
 CURRENT BLOCK:
 Type: {block_type}
 Content: {current_plain_text}
 
 FORMATTING TO PRESERVE:{formatting_context}
 DETAILED FORMATTING:{detailed_formatting}
 
 TASK: {enhancement_prompt}
 
 CONTEXT-AWARE INSTRUCTIONS:
 - Consider the pattern from recent blocks to make intelligent decisions
 - If this is a keyword/header that fits a structural pattern, be conservative  
 - If this is content within an established flow, apply full enhancement/translation
 - For single words: check if they're labels/headers vs. translatable content
 - Short content like "Instructions" after setup content should be processed
 - Standalone structural terms might be kept unchanged
 
 IMPORTANT: 
 - Return ONLY the improved text content
 - Do NOT add formatting markers like **bold** or *italic*
 - If there's a leading emoji, START your response with that exact emoji
 - Keep the core meaning but make it clearer and more accessible
 - Maintain the same general structure and emphasis patterns
 - CRITICAL: Do NOT change or remove any hyperlinks; keep ALL linked text exactly intact
 - Do NOT modify Bible version abbreviations in parentheses like (NIV), (YLT), (ESV), etc.
 
 IMPROVED CONTENT:"""
            
            # Get AI enhancement
            try:
                enhanced_content = ai_handler.get_response(ai_prompt)
                
                # Log AI interaction
                from orchestrator import log_ai_interaction
                log_ai_interaction(ai_prompt, enhanced_content, ai_handler.model_type, f"BLOCK_UPDATE_{block_type}")
                
                if not enhanced_content or len(enhanced_content.strip()) < 1:
                    return {'success': False, 'error': 'Invalid AI response'}
                
                # Check if AI says no changes needed
                if enhanced_content.strip().upper() in ['NO CHANGES', 'NO CHANGE', 'NOCHANGES']:
                    logging.info(f"✅ AI determined no changes needed for {block_type} block")
                    return {'success': True, 'skipped': True, 'reason': 'AI determined no changes needed'}
                
                # Apply intelligent update with formatting info
                result = self._apply_intelligent_update(
                    block_id, block_type, enhanced_content.strip(), 
                    rich_text_array, current_plain_text, current_block, formatting_info
                )
                
                return {
                    'success': result,
                    'original_length': len(current_plain_text),
                    'enhanced_length': len(enhanced_content),
                    'enhanced_text': enhanced_content.strip(),  # For context tracking
                    'block_type': block_type
                }
                
            except Exception as ai_error:
                return {'success': False, 'error': f'AI error: {str(ai_error)}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def intelligent_block_update(self, block_id, enhancement_prompt, ai_handler):
        """
        Legacy method - delegates to context-aware version
        
        Args:
            block_id (str): Block ID to update
            enhancement_prompt (str): What kind of enhancement to apply
            ai_handler: AI handler for real-time assistance
            
        Returns:
            dict: Update results
        """
        return self.intelligent_block_update_with_context(block_id, enhancement_prompt, ai_handler, [])
    
    def _sanitize_markdown_inline(self, text: str, block_type: str) -> str:
        """Remove markdown markers like **, *, __, and leading #### for headings to avoid literal markers in Notion."""
        original = text
        if block_type.startswith('heading_'):
            text = re.sub(r"^\s*#{1,6}\s*", "", text)
        # Remove bold/italic/code markers while keeping content
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        text = re.sub(r"_(.*?)_", r"\1", text)
        text = re.sub(r"`(.*?)`", r"\1", text)
        if text != original:
            logging.info("🧹 Sanitized markdown markers from AI output")
        return text

    def _collect_preserved_spans(self, original_rich_text):
        """Collect spans with annotations and links from original rich text for reinjection."""
        spans = []
        for part in original_rich_text:
            text_obj = part.get('text', {})
            link_obj = text_obj.get('link') or {}
            url = link_obj.get('url')
            annotations = part.get('annotations', {}) or {}
            color = annotations.get('color')
            has_any = url or any(v for k, v in annotations.items() if k != 'color') or (color and color != 'default')
            if has_any:
                spans.append({
                    'text': part.get('plain_text') or text_obj.get('content') or '',
                    'url': url,
                    'annotations': annotations
                })
        return [s for s in spans if s['text']]

    def _apply_spans_to_text(self, text: str, spans):
        """Build a Notion rich_text array for `text`, reapplying spans where their substrings are found."""
        # Start with one plain run
        runs = [{
            'text': text,
            'annotations': {
                'bold': False, 'italic': False, 'strikethrough': False,
                'underline': False, 'code': False, 'color': 'default'
            },
            'link': None
        }]

        def split_run(run_idx, start, end, new_ann, new_link):
            run = runs[run_idx]
            s = run['text']
            before, middle, after = s[:start], s[start:end], s[end:]
            new_runs = []
            if before:
                new_runs.append({**run, 'text': before})
            if middle:
                ann = run['annotations'].copy()
                # Merge annotations (preserve existing + add new)
                if new_ann:
                    for key, value in new_ann.items():
                        if key == 'color' and value != 'default':
                            ann[key] = value  # Override color
                        elif isinstance(value, bool) and value:
                            ann[key] = True   # Enable boolean annotations
                new_runs.append({
                    'text': middle,
                    'annotations': ann,
                    'link': new_link if new_link else run.get('link')
                })
            if after:
                new_runs.append({**run, 'text': after})
            runs[run_idx:run_idx+1] = new_runs

        # Sort spans by text length (longest first) for better matching
        sorted_spans = sorted(spans, key=lambda s: len(s.get('text', '')), reverse=True)
        
        # Apply each span in order
        for span in sorted_spans:
            needle = (span.get('text', '') or '').strip()
            if not needle or len(needle) < 2:  # Skip very short spans
                continue
                
            # Enhanced fuzzy matching - try exact match first, then partial
            matched = False
            for search_text in [needle, needle.lower(), needle.replace(' ', '')]:
                if matched:
                    break
                    
                for idx in range(len(runs)):
                    if matched:
                        break
                    r = runs[idx]
                    hay = r['text']
                    
                    # Try different matching strategies
                    positions = []
                    
                    # Exact match
                    pos = hay.find(search_text)
                    if pos != -1:
                        positions.append((pos, pos + len(search_text), len(search_text)))
                    
                    # Case-insensitive match
                    pos = hay.lower().find(search_text.lower())
                    if pos != -1 and pos not in [p[0] for p in positions]:
                        positions.append((pos, pos + len(search_text), len(search_text)))
                    
                    # Use the best match (prefer exact, then case-insensitive)
                    if positions:
                        start_pos, end_pos, match_len = positions[0]
                        split_run(idx, start_pos, end_pos, span.get('annotations') or {}, span.get('url'))
                        matched = True
                        break
                        
        # Convert runs to Notion rich_text
        rich = []
        for r in runs:
            if r['text']:  # Only include non-empty text
                text_obj = {'content': r['text']}
                if r.get('link'):
                    text_obj['link'] = {'url': r['link']}
                rich.append({
                    'type': 'text',
                    'text': text_obj,
                    'annotations': r['annotations']
                })
        return rich if rich else [{"type": "text", "text": {"content": text}}]

    def _create_smart_rich_text_structure(self, enhanced_text, original_rich_text, formatting_info=None, block_type: str = ''):
        """Create enhanced rich text using hybrid markdown + color tag parsing."""
        # Handle emoji preservation first
        if formatting_info and formatting_info.get('leading_emoji'):
            emoji = formatting_info['leading_emoji']
            if not enhanced_text.startswith(emoji):
                enhanced_text = emoji + ' ' + enhanced_text.lstrip()
                logging.info(f"🚀 Restored leading emoji: {emoji}")

        # Use hybrid markdown + color tag parser
        rich_text_array = self._parse_hybrid_markdown_to_rich_text(enhanced_text)
        
        # Preserve any links from original that weren't captured by the AI
        original_links = []
        for rt in original_rich_text:
            link_info = rt.get('text', {}).get('link')
            if link_info and link_info.get('url'):
                original_links.append({
                    'text': rt.get('text', {}).get('content', ''),
                    'url': link_info['url']
                })
        
        # If we have important links that weren't preserved, try to re-inject them
        if original_links:
            # Simple approach: if the link text still exists somewhere in the enhanced text,
            # find it and convert it to a link in the rich text array
            for link in original_links:
                link_text = link['text'].strip()
                if link_text and len(link_text) > 3:  # Only try to preserve substantial link text
                    # Validate URL first
                    valid_url = self._validate_and_convert_url(link['url'])
                    if valid_url:
                        for rt_item in rich_text_array:
                            content = rt_item.get('text', {}).get('content', '')
                            if link_text in content:
                                # Found the link text, convert it to a link
                                rt_item['text']['link'] = {'url': valid_url}
                                logging.info(f"🔗 Preserved link: {link_text} -> {valid_url[:50]}...")
                                break
                    else:
                        logging.warning(f"⚠️ Skipped preserving invalid link: {link_text} -> {link['url']}")
        
        return rich_text_array
    
    def _build_update_payload(self, block_type, rich_text_array, current_block):
        """
        Build the appropriate update payload for the block type
        """
        if block_type == 'paragraph':
            return {"paragraph": {"rich_text": rich_text_array}}
        elif block_type.startswith('heading_'):
            return {block_type: {"rich_text": rich_text_array}}
        elif block_type == 'bulleted_list_item':
            return {"bulleted_list_item": {"rich_text": rich_text_array}}
        elif block_type == 'numbered_list_item':
            return {"numbered_list_item": {"rich_text": rich_text_array}}
        elif block_type == 'quote':
            return {"quote": {"rich_text": rich_text_array}}
        elif block_type == 'to_do':
            checked = current_block.get('to_do', {}).get('checked', False)
            return {"to_do": {"rich_text": rich_text_array, "checked": checked}}
        elif block_type == 'toggle':
            return {"toggle": {"rich_text": rich_text_array}}
        elif block_type == 'callout':
            callout_props = current_block.get('callout', {})
            return {
                "callout": {
                    "rich_text": rich_text_array,
                    "icon": callout_props.get('icon', {"type": "emoji", "emoji": "📝"}),
                    "color": callout_props.get('color', "default")
                }
            }
        elif block_type == 'image':
            return {"image": {"caption": rich_text_array}}
        elif block_type == 'video':
            return {"video": {"caption": rich_text_array}}
        elif block_type == 'file':
            return {"file": {"caption": rich_text_array}}
        elif block_type == 'pdf':
            return {"pdf": {"caption": rich_text_array}}
        elif block_type == 'audio':
            return {"audio": {"caption": rich_text_array}}
        elif block_type == 'bookmark':
            return {"bookmark": {"caption": rich_text_array}}
        
        return None
    
    def _is_block_in_synced_content(self, block, all_blocks):
        """
        Check if a block is inside synced content by walking its parents
        using the flattened cached blocks (which include parent info).
        """
        try:
            if not block:
                return False
            parent = block.get('parent') or {}
            if not parent:
                return False
            id_to_block = {b.get('id'): b for b in all_blocks if isinstance(b, dict) and b.get('id')}
            # Climb the ancestor chain as long as parent is a block
            while parent and parent.get('type') == 'block_id':
                parent_id = parent.get('block_id')
                if not parent_id:
                    break
                parent_block = id_to_block.get(parent_id)
                if not parent_block:
                    # Parent might not be in cached list; stop here
                    break
                if parent_block.get('type') == 'synced_block':
                    return True
                parent = parent_block.get('parent') or {}
        except Exception as e:
            logging.warning(f"⚠️ Could not determine synced ancestry from cache: {e}")
        return False

    def _is_block_or_ancestor_synced_api(self, block_id: str) -> bool:
        """Hard guard using API: return True if this block or any ancestor is a synced_block."""
        try:
            block = self.client.blocks.retrieve(block_id)
            if block.get('type') == 'synced_block':
                return True
            parent = block.get('parent') or {}
            while parent and parent.get('type') == 'block_id':
                parent_id = parent.get('block_id')
                if not parent_id:
                    break
                parent_block = self.client.blocks.retrieve(parent_id)
                if parent_block.get('type') == 'synced_block':
                    return True
                parent = parent_block.get('parent') or {}
        except Exception as e:
            logging.warning(f"⚠️ API ancestry check failed for {block_id}: {e}")
        return False
    
    def _find_toggle_children_blocks(self, page_id):
        """
        Find all blocks that are children of toggle blocks
        
        Args:
            page_id (str): Notion page ID
            
        Returns:
            list: All blocks that are inside toggles
        """
        toggle_children = []
        
        try:
            # Get all blocks
            all_blocks = self._load_cached_blocks(page_id)
            if not all_blocks:
                return []
            
            # Find toggle blocks
            toggle_blocks = [b for b in all_blocks if b.get('type') == 'toggle']
            
            for toggle_block in toggle_blocks:
                if toggle_block.get('has_children'):
                    try:
                        children = self.get_toggle_children(toggle_block['id'])
                        for child in children:
                            # Skip synced blocks even in toggles
                            if child.get('type') != 'synced_block':
                                toggle_children.append(child)
                                logging.info(f"🔄 Found toggle child: {child.get('type')} in {toggle_block['id'][:8]}...")
                    except Exception as e:
                        logging.warning(f"⚠️ Could not get toggle children: {e}")
            
            return toggle_children
            
        except Exception as e:
            logging.error(f"❌ Error finding toggle children: {e}")
            return []
    
    def _extract_emoji_and_formatting_info(self, rich_text_array):
        """
        Extract comprehensive formatting information from original rich text
        
        Args:
            rich_text_array (list): Original rich text structure
            
        Returns:
            dict: Comprehensive formatting information to preserve
        """
        formatting_info = {
            'leading_emoji': '',
            'has_bold': False,
            'has_italic': False,
            'has_strikethrough': False,
            'has_underline': False,
            'has_code': False,
            'has_colors': False,
            'color_info': {},
            'has_links': False,
            'link_info': [],
            'formatting_patterns': [],
            'rich_spans': []
        }
        
        if not rich_text_array:
            return formatting_info
        
        # Check first element for emoji
        first_element = rich_text_array[0]
        if first_element and first_element.get('text', {}).get('content'):
            content = first_element['text']['content']
            # Enhanced emoji detection
            if content and len(content) > 0:
                first_char = content[0]
                # Check if first character is emoji (Unicode range check)
                if ord(first_char) > 127:
                    # Find end of emoji sequence (handles compound emojis)
                    emoji_end = 1
                    while emoji_end < len(content) and ord(content[emoji_end]) > 127:
                        emoji_end += 1
                    # Extract emoji including space separator
                    potential_emoji = content[:emoji_end]
                    if emoji_end < len(content) and content[emoji_end] == ' ':
                        emoji_end += 1
                        potential_emoji = content[:emoji_end]
                    if ord(first_char) >= 0x1F300 or len(potential_emoji) > 1:
                        formatting_info['leading_emoji'] = potential_emoji.strip()
        
        # Comprehensive formatting pattern analysis
        for element in rich_text_array:
            annotations = element.get('annotations', {})
            text_content = element.get('text', {}).get('content', '')
            link_info = element.get('text', {}).get('link')
            
            # Track all annotation types
            if annotations:
                if annotations.get('bold'):
                    formatting_info['has_bold'] = True
                if annotations.get('italic'):
                    formatting_info['has_italic'] = True
                if annotations.get('strikethrough'):
                    formatting_info['has_strikethrough'] = True
                if annotations.get('underline'):
                    formatting_info['has_underline'] = True
                if annotations.get('code'):
                    formatting_info['has_code'] = True
                
                # Enhanced color tracking
                color = annotations.get('color', 'default')
                if color and color != 'default':
                    formatting_info['has_colors'] = True
                    if color not in formatting_info['color_info']:
                        formatting_info['color_info'][color] = []
                    formatting_info['color_info'][color].append(text_content)
            
            # Link information tracking
            if link_info and link_info.get('url'):
                formatting_info['has_links'] = True
                formatting_info['link_info'].append({
                    'text': text_content,
                    'url': link_info['url']
                })
            
            # Store comprehensive formatting patterns
            if annotations or link_info:
                pattern = {
                    'text': text_content,
                    'annotations': annotations,
                    'link': link_info
                }
                formatting_info['formatting_patterns'].append(pattern)
            
            # Create rich span info for detailed preservation
            if text_content:
                span_info = {
                    'text': text_content,
                    'bold': annotations.get('bold', False),
                    'italic': annotations.get('italic', False),
                    'strikethrough': annotations.get('strikethrough', False),
                    'underline': annotations.get('underline', False),
                    'code': annotations.get('code', False),
                    'color': annotations.get('color', 'default'),
                    'link_url': link_info.get('url') if link_info else None
                }
                formatting_info['rich_spans'].append(span_info)
        
        return formatting_info

    def _build_detailed_formatting_description(self, formatting_info):
        """
        Create a detailed, human-readable description of formatting for AI context
        
        Args:
            formatting_info (dict): Comprehensive formatting information
            
        Returns:
            str: Human-readable formatting description for AI prompts
        """
        details = []
        
        if formatting_info.get('leading_emoji'):
            details.append(f"- Starts with emoji: '{formatting_info['leading_emoji']}'")
        
        # Basic formatting flags
        formatting_flags = []
        if formatting_info.get('has_bold'):
            formatting_flags.append("bold text")
        if formatting_info.get('has_italic'):
            formatting_flags.append("italic text")
        if formatting_info.get('has_strikethrough'):
            formatting_flags.append("strikethrough text")
        if formatting_info.get('has_underline'):
            formatting_flags.append("underlined text")
        if formatting_info.get('has_code'):
            formatting_flags.append("code formatting")
            
        if formatting_flags:
            details.append(f"- Contains: {', '.join(formatting_flags)}")
        
        # Color details with formatting examples  
        color_info = formatting_info.get('color_info', {})
        if color_info:
            color_details = []
            for color, texts in color_info.items():
                sample_text = texts[0][:20] + "..." if len(texts[0]) > 20 else texts[0]
                color_details.append(f"[color:{color}]{sample_text}[/color]")
            details.append(f"- Original colors to preserve: {', '.join(color_details)}")
        
        # Link details
        link_info = formatting_info.get('link_info', [])
        if link_info:
            link_details = []
            for link in link_info[:3]:  # Show first 3 links
                link_text = link['text'][:20] + "..." if len(link['text']) > 20 else link['text']
                link_details.append(f"'{link_text}' → {link['url'][:30]}...")
            details.append(f"- Contains {len(link_info)} link(s): {', '.join(link_details)}")
            details.append("- CRITICAL: Keep these links intact in your response")
        
        # Rich span analysis
        rich_spans = formatting_info.get('rich_spans', [])
        if rich_spans:
            # Count different formatting combinations
            combinations = {}
            for span in rich_spans:
                if span.get('link_url') or any([span.get('bold'), span.get('italic'), span.get('strikethrough'), span.get('underline'), span.get('code')]) or span.get('color', 'default') != 'default':
                    combo_parts = []
                    if span.get('bold'): combo_parts.append("bold")
                    if span.get('italic'): combo_parts.append("italic")
                    if span.get('code'): combo_parts.append("code")
                    if span.get('color', 'default') != 'default': combo_parts.append(f"{span['color']}-colored")
                    if span.get('link_url'): combo_parts.append("linked")
                    
                    combo_key = "+".join(combo_parts) if combo_parts else "plain"
                    if combo_key not in combinations:
                        combinations[combo_key] = []
                    combinations[combo_key].append(span['text'][:15])
            
            if combinations:
                combo_details = []
                for combo, texts in combinations.items():
                    sample = texts[0] + "..." if len(texts[0]) == 15 else texts[0]
                    combo_details.append(f"{combo} ('{sample}')")
                details.append(f"- Formatting patterns: {', '.join(combo_details)}")
        
        if not details:
            return "- Plain text, no special formatting"
            
        return "\n".join(details)

    def _validate_and_clean_ai_output(self, text):
        """
        Validate and clean AI output to fix common formatting issues
        """
        if not text:
            return text
            
        # Fix common malformed patterns
        text = text.strip()
        
        # Fix broken color tags (missing closing tags, etc.)
        # Match [color:red]text without proper closing
        text = re.sub(r'\[color:(\w+)\]([^[]*?)(?!\[/color\])', r'[color:\1]\2[/color]', text)
        
        # Fix duplicate links like: **[text](url)**[text](url)[/color]
        # Remove duplicated link patterns
        text = re.sub(r'(\[[^\]]+\]\([^)]+\))\1+', r'\1', text)
        
        # Fix malformed color + link combinations
        # Pattern: **[text](url)**text[/color] -> **[text](url)**
        text = re.sub(r'(\*\*\[[^\]]+\]\([^)]+\)\*\*)[^[]*?\[/color\]', r'\1', text)
        
        # Remove orphaned color closing tags
        text = re.sub(r'\[/color\](?!\s*\[color:)', '', text)
        
        # Fix nested markdown issues (***text** -> ***text***)
        text = re.sub(r'\*\*\*([^*]+)\*\*(?!\*)', r'***\1***', text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def _validate_and_convert_url(self, url):
        """
        Validate and convert URLs to formats acceptable by Notion
        
        Args:
            url (str): Original URL from link
            
        Returns:
            str or None: Valid absolute URL or None if invalid
        """
        if not url or not url.strip():
            return None
            
        url = url.strip()
        
        # Already absolute URL
        if url.startswith(('http://', 'https://')):
            return url
            
        # Notion relative page URL pattern: /12672d5af2de80d4aaf8d1875acbc...
        if url.startswith('/') and len(url) > 20:
            # Extract page ID (remove leading slash)
            page_id = url[1:]
            # Convert to absolute Notion URL
            absolute_url = f"https://www.notion.so/{page_id}"
            logging.info(f"🔗 Converted relative URL: {url} -> {absolute_url}")
            return absolute_url
            
        # Mailto links
        if url.startswith('mailto:'):
            return url
            
        # Invalid/unsupported URL format
        logging.warning(f"⚠️ Skipping invalid URL format: {url}")
        return None

    def _parse_hybrid_markdown_to_rich_text(self, text):
        """
        Parse hybrid markdown + color tags to Notion rich text array
        
        Supported syntax:
        - **bold** 
        - *italic*
        - ***bold+italic***
        - ~~strikethrough~~
        - `code`
        - [color:red]text[/color]
        - Links: [text](url) or preserved from original
        """
        if not text or not text.strip():
            return [{"type": "text", "text": {"content": text or ""}}]
        
        # Clean and validate AI output first
        text = self._validate_and_clean_ai_output(text)
        
        # Color mapping for Notion
        color_map = {
            'red': 'red',
            'blue': 'blue', 
            'green': 'green',
            'yellow': 'yellow',
            'orange': 'orange',
            'purple': 'purple',
            'pink': 'pink',
            'gray': 'gray',
            'grey': 'gray',
            'brown': 'brown'
        }
        
        # Step 1: Extract and preserve links first (to avoid conflicts)
        links = []
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(link_pattern, text):
            links.append({
                'start': match.start(),
                'end': match.end(),
                'text': match.group(1),
                'url': match.group(2),
                'placeholder': f"__LINK_{len(links)}__"
            })
        
        # Replace links with placeholders to avoid conflicts during formatting parsing
        working_text = text
        for i, link in enumerate(reversed(links)):  # Reverse to maintain positions
            working_text = working_text[:link['start']] + link['placeholder'] + working_text[link['end']:]
        
        # Regex patterns for different formatting (order matters - most specific first)
        patterns = [
            # Color tags first (most specific)
            (r'\[color:(\w+)\](.*?)\[/color\]', 'color'),
            # Triple asterisks (bold+italic) before double/single
            (r'\*\*\*(.*?)\*\*\*', 'bold_italic'),
            # Double asterisks (bold) before single
            (r'\*\*(.*?)\*\*', 'bold'),
            # Single asterisks (italic) - avoid conflicts with bold patterns
            (r'(?<!\*)\*([^*]+?)\*(?!\*)', 'italic'),
            # Other formatting
            (r'~~(.*?)~~', 'strikethrough'), 
            (r'`([^`]+?)`', 'code'),
        ]
        
        # Step 2: Find all formatting tokens in the working text (with link placeholders)
        format_tokens = []
        for pattern, format_type in patterns:
            for match in re.finditer(pattern, working_text):
                start, end = match.span()
                content = match.group(1) if format_type != 'color' else match.group(2)
                color = match.group(1) if format_type == 'color' else None
                format_tokens.append({
                    'start': start,
                    'end': end, 
                    'type': format_type,
                    'content': content,
                    'color': color_map.get(color.lower()) if color else None
                })
        
        # Sort by start position
        format_tokens.sort(key=lambda x: x['start'])
        
        # Step 3: Build rich text array from working text 
        rich_text = []
        current_pos = 0
        
        for token in format_tokens:
            # Add any plain text before this token
            if token['start'] > current_pos:
                plain_part = working_text[current_pos:token['start']]
                if plain_part:
                    rich_text.append({
                        "type": "text",
                        "text": {"content": plain_part}
                    })
            
            # Add the formatted token
            annotations = {
                'bold': token['type'] in ['bold', 'bold_italic'],
                'italic': token['type'] in ['italic', 'bold_italic'],
                'strikethrough': token['type'] == 'strikethrough',
                'underline': False,
                'code': token['type'] == 'code',
                'color': token['color'] or 'default'
            }
            
            rich_text.append({
                "type": "text",
                "text": {"content": token['content']},
                "annotations": annotations
            })
            
            current_pos = token['end']
        
        # Add any remaining plain text
        if current_pos < len(working_text):
            remaining_text = working_text[current_pos:]
            if remaining_text:
                rich_text.append({
                    "type": "text", 
                    "text": {"content": remaining_text}
                })
        
        # If no formatting was found, use the working text
        if not rich_text:
            rich_text = [{"type": "text", "text": {"content": working_text}}]
        
        # Step 4: Restore link placeholders with actual links (with validation)
        for i, item in enumerate(rich_text):
            content = item.get('text', {}).get('content', '')
            for link in links:
                if link['placeholder'] in content:
                    # Validate and convert URL
                    valid_url = self._validate_and_convert_url(link['url'])
                    
                    # Replace placeholder with link text
                    new_content = content.replace(link['placeholder'], link['text'])
                    item['text']['content'] = new_content
                    
                    # Only add link property if URL is valid
                    if valid_url:
                        item['text']['link'] = {'url': valid_url}
                        logging.info(f"🔗 Restored link: {link['text']} -> {valid_url[:50]}...")
                    else:
                        logging.warning(f"⚠️ Skipped invalid link: {link['text']} -> {link['url']}")
            
        return rich_text

    def _apply_intelligent_update(self, block_id, block_type, enhanced_text, original_rich_text, original_plain_text, current_block, formatting_info=None):
        """
        Apply the enhanced text while preserving as much structure as possible
        """
        try:
            # Trim to API limits
            if len(enhanced_text) > 1900:
                enhanced_text = enhanced_text[:1900] + "..."
            
            # Create structure-aware rich text with link/annotation preservation
            enhanced_rich_text = self._create_smart_rich_text_structure(
                enhanced_text, original_rich_text, formatting_info, block_type
            )
            
            # Build update payload based on block type
            update_data = self._build_update_payload(block_type, enhanced_rich_text, current_block)
            
            if not update_data:
                return False
 
            # Apply the update
            self.client.blocks.update(block_id, **update_data)
            return True
            
        except Exception as e:
            logging.error(f"❌ Intelligent update failed: {e}")
            return False