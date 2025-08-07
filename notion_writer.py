#!/usr/bin/env python3
"""
Notion Writer Module

This module provides functionality to write back to Notion pages,
including finding specific blocks and updating their content.
"""

import os
import json
import logging
import re
from pathlib import Path
from notion_client import Client
from dotenv import load_dotenv
from file_finder import find_debug_file_by_page_id_only

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
    
    def create_bulleted_list_item_block(self, text):
        """
        Create a bulleted list item block data structure
        
        Args:
            text (str): List item text
            
        Returns:
            dict: Block data for bulleted list item
        """
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
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
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Handle headings
            if line.startswith('### '):
                blocks.append(self.create_heading_block(line[4:], 3))
            elif line.startswith('## '):
                blocks.append(self.create_heading_block(line[3:], 2))
            elif line.startswith('# '):
                blocks.append(self.create_heading_block(line[2:], 1))
            # Handle special formatting
            elif line.strip() == '---':
                blocks.append(self.create_divider_block())
            elif line.startswith('> '):
                # Treat as callout
                blocks.append(self.create_callout_block(line[2:], "📝", "gray_background"))
            # Handle bullet points
            elif line.startswith('- ') or line.startswith('• '):
                blocks.append(self.create_bulleted_list_item_block(line[2:]))
            # Handle numbered lists (convert to bullets for simplicity)
            elif re.match(r'^\d+\. ', line):
                text = line.split('. ', 1)[1] if '. ' in line else line
                blocks.append(self.create_bulleted_list_item_block(text))
            # Regular paragraph
            else:
                if line.strip():  # Only create non-empty paragraphs
                    blocks.append(self.create_paragraph_block(line))
        
        return blocks
    
    def find_activity_blocks(self, page_id):
        """
        Find blocks that represent activities (looking for activity markers)
        
        Args:
            page_id (str): The Notion page ID
            
        Returns:
            list: List of blocks that appear to be activities
        """
        def is_activity_block(block):
            block_type = block.get('type')
            text_content = self._extract_plain_text_from_block(block)
            
            # Check for activity-related block types
            if block_type in ['toggle', 'callout']:
                return True  # These often contain activities
            
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
        
        return self.find_blocks_by_criteria(page_id, is_activity_block)
    
    def insert_trainer_questions_section(self, page_id, questions_markdown):
        """
        Insert a "Trainer Evaluation Questions" section with the provided questions
        
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
            
            # Append to the page
            return self.append_blocks_to_page(page_id, section_blocks)
            
        except Exception as e:
            logging.error(f"❌ Error inserting trainer questions: {e}")
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
            updatable_blocks = []
            for block in all_blocks:
                block_type = block.get('type')
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
                                
                                self.update_block_text(block['id'], trimmed_text)
                                updated_count += 1
                                logging.info(f"📝 Updated block with enhanced content")
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