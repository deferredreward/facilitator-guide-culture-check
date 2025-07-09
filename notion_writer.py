#!/usr/bin/env python3
"""
Notion Writer Module

This module provides functionality to write back to Notion pages,
including finding specific blocks and updating their content.
"""

import os
import json
import logging
from pathlib import Path
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
            saved_pages_dir = Path("saved_pages")
            debug_file = saved_pages_dir / f"notion_page_{page_id}_debug.json"
            
            if not debug_file.exists():
                logging.warning(f"⚠️ No cached data found at {debug_file}")
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
        else:
            return ""
        
        # Extract plain text from rich text array
        if not rich_text:
            return ""
        
        text_parts = []
        for text_part in rich_text:
            text_parts.append(text_part.get('plain_text', ''))
        
        return ''.join(text_parts)
    
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
    
    def update_block_text(self, block_id, new_text):
        """
        Update a block's text content
        
        Args:
            block_id (str): The block ID to update
            new_text (str): The new text content
            
        Returns:
            dict: The updated block response
        """
        try:
            # Get the current block to determine its type
            current_block = self.client.blocks.retrieve(block_id)
            block_type = current_block.get('type')
            
            if not block_type:
                raise ValueError(f"Could not determine block type for {block_id}")
            
            # Create the rich text array for the new content
            new_rich_text = [
                {
                    "type": "text",
                    "text": {
                        "content": new_text
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
            
            # Update the block
            response = self.client.blocks.update(block_id, **update_data)
            logging.info(f"✅ Block {block_id} updated successfully")
            return response
            
        except Exception as e:
            logging.error(f"❌ Error updating block {block_id}: {e}")
            raise
    
    def _get_all_blocks_recursively(self, block_id):
        """
        Recursively get all blocks including nested children (fallback for when cached data isn't available)
        
        Args:
            block_id (str): The block ID to start from
            
        Returns:
            list: List of all blocks
        """
        logging.warning("⚠️ Using API calls to get blocks - this is slower than using cached data")
        all_blocks = []
        
        def get_blocks(b_id):
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