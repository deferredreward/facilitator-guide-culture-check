#!/usr/bin/env python3
"""
AI Translator Module for Notion Pages

This module provides functionality to translate Notion pages block by block,
preserving formatting and emojis while carefully translating content using AI.
"""

import os
import sys
import argparse
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from ai_handler import create_ai_handler
from notion_writer import NotionWriter

# Add utils directory to path for utility imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from markdown_utils import clean_markdown_content
from file_finder import find_markdown_file_by_page_id

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def get_page_id_and_language():
    """Get page ID and target language from command line arguments or prompt user"""
    parser = argparse.ArgumentParser(description='Translate Notion page content using AI')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    parser.add_argument('--ai', choices=['claude', 'anthropic', 'gemini', 'openai', 'xai'], default='gemini',
                       help='AI model to use (default: gemini)')
    parser.add_argument('--tar-lang', '-tl', help='Target language (common name or ISO code)')
    parser.add_argument('--blocks', type=int, help='Limit number of blocks to translate (for testing)')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to translate:")
        page_id = input().strip()
        
        if not page_id:
            logging.error("❌ No page ID provided")
            sys.exit(1)
    
    # Get target language
    target_language = args.tar_lang
    if not target_language:
        print("Enter target language (common name like 'Spanish' or ISO code like 'es'):")
        target_language = input().strip()
        
        if not target_language:
            logging.error("❌ No target language provided")
            sys.exit(1)
    
    return page_id, args.ai, target_language, args.blocks

def validate_target_language(target_language, ai_handler):
    """
    Use AI to validate if the target language is clear and unambiguous
    
    Args:
        target_language (str): The target language provided by user
        ai_handler: AI handler for validation
        
    Returns:
        bool: True if language is clear, False if needs clarification
    """
    validation_prompt = f"""
Is it clear what language the user wants to translate into based on this input: "{target_language}"?

Respond with ONLY "yes" or "no" - nothing else.

If the language is ambiguous (like "Arabic" which could be MSA, Egyptian Arabic, etc.), respond "no".
If it's a clear language specification (like "Spanish", "French", "es", "fr", "Egyptian Arabic", "MSA"), respond "yes".
"""
    
    try:
        response = ai_handler.get_response(validation_prompt).strip().lower()
        logging.info(f"🤖 AI language validation response: {response}")
        return response == "yes"
    except Exception as e:
        logging.error(f"❌ Error validating language: {e}")
        return False

def find_markdown_file(page_id):
    """Find the markdown file for the given page ID in saved_pages directory"""
    markdown_file = find_markdown_file_by_page_id(page_id)
    
    if not markdown_file:
        logging.error(f"❌ Markdown file not found for page_id: {page_id}")
        return None
    
    logging.info(f"✅ Found markdown file: {markdown_file}")
    return markdown_file

def read_markdown_content(file_path):
    """Read the markdown content from the file and clean it"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logging.info(f"✅ Read {len(content)} characters from markdown file")
        
        # Clean the content to reduce tokens
        cleaned_content = clean_markdown_content(content)
        logging.info(f"✅ Cleaned content length: {len(cleaned_content)} characters")
        
        return cleaned_content
    except Exception as e:
        logging.error(f"❌ Error reading markdown file: {e}")
        return None

def load_translation_prompt_from_txt(path: str = "prompts.txt") -> str:
    """Load the Translation prompt from prompts.txt."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception:
        # Fallback to a safe generic translation prompt
        return (
            "You are an expert translator specializing in technical and educational content.\n\n"
            "Please translate the following content while preserving:\n"
            "1. ALL formatting (markdown, bullets, numbers, etc.)\n"
            "2. ALL emojis exactly as they appear\n"
            "3. Technical terms and proper nouns (translate explanations but keep key terms)\n"
            "4. The structure and flow of the original text\n"
            "5. Biblical references and version abbreviations like (NIV), (ESV), etc.\n\n"
            "Target Language: {target_language}\n\n"
            "Content to translate:\n\n{content}\n\n"
            "Please return the translated content maintaining all original formatting."
        )

    start_idx = text.find("# Translation:")
    if start_idx == -1:
        return (
            "You are an expert translator specializing in technical and educational content.\n\n"
            "Please translate the following content while preserving:\n"
            "1. ALL formatting (markdown, bullets, numbers, etc.)\n"
            "2. ALL emojis exactly as they appear\n"
            "3. Technical terms and proper nouns (translate explanations but keep key terms)\n"
            "4. The structure and flow of the original text\n"
            "5. Biblical references and version abbreviations like (NIV), (ESV), etc.\n\n"
            "Target Language: {target_language}\n\n"
            "Content to translate:\n\n{content}\n\n"
            "Please return the translated content maintaining all original formatting."
        )
    section = text[start_idx:]
    q1 = section.find('"""')
    if q1 == -1:
        return (
            "You are an expert translator specializing in technical and educational content.\n\n"
            "Please translate the following content while preserving:\n"
            "1. ALL formatting (markdown, bullets, numbers, etc.)\n"
            "2. ALL emojis exactly as they appear\n"
            "3. Technical terms and proper nouns (translate explanations but keep key terms)\n"
            "4. The structure and flow of the original text\n"
            "5. Biblical references and version abbreviations like (NIV), (ESV), etc.\n\n"
            "Target Language: {target_language}\n\n"
            "Content to translate:\n\n{content}\n\n"
            "Please return the translated content maintaining all original formatting."
        )
    q2 = section.find('"""', q1 + 3)
    if q2 == -1:
        return (
            "You are an expert translator specializing in technical and educational content.\n\n"
            "Please translate the following content while preserving:\n"
            "1. ALL formatting (markdown, bullets, numbers, etc.)\n"
            "2. ALL emojis exactly as they appear\n"
            "3. Technical terms and proper nouns (translate explanations but keep key terms)\n"
            "4. The structure and flow of the original text\n"
            "5. Biblical references and version abbreviations like (NIV), (ESV), etc.\n\n"
            "Target Language: {target_language}\n\n"
            "Content to translate:\n\n{content}\n\n"
            "Please return the translated content maintaining all original formatting."
        )
    return section[q1 + 3:q2].strip()

def get_block_level_translation_instructions(target_language, path: str = "prompts.txt") -> str:
    """Return concise translation instructions for individual blocks."""
    return f"""Translate to {target_language}. Keep all formatting, emojis, proper nouns, and links exactly as they are. Preserve any linked text functionality. Add context like "lihat:" before links if helpful. Return ONLY translated text:"""

def validate_translation_response(response, original_text, target_language):
    """
    Validate AI translation response to prevent prompt leakage
    
    Args:
        response (str): AI translation response
        original_text (str): Original text that was translated
        target_language (str): Target language
        
    Returns:
        tuple: (is_valid, cleaned_response)
    """
    if not response:
        return False, ""
    
    response = response.strip()
    
    # Check for prompt leakage indicators
    prompt_indicators = [
        "CRITICAL REQUIREMENTS",
        "TRANSLATION GUIDELINES", 
        "SPECIFIC PRESERVATION",
        "TASK:",
        "IMPORTANT:",
        "You are an expert",
        "Translate the following",
        f"to {target_language}",
        "Keep ALL formatting"
    ]
    
    # If response contains prompt language, it's invalid
    for indicator in prompt_indicators:
        if indicator in response:
            logging.warning(f"🚫 Detected prompt leakage: '{indicator}' in response")
            return False, ""
    
    # Response should be reasonable length (but allow for language differences)
    # For very short text, allow more flexibility
    if len(original_text.strip()) < 5:
        # Very short text - allow up to 50 characters response
        if len(response) > 50:
            logging.warning(f"🚫 Response too long for short text ({len(response)} chars vs {len(original_text)} original)")
            return False, ""
    else:
        # Normal text - allow up to 5x expansion for language differences
        if len(response) > len(original_text) * 5:
            logging.warning(f"🚫 Response too long ({len(response)} chars vs {len(original_text)} original)")
            return False, ""
    
    return True, response

def get_ai_translation_prompt(content, target_language):
    """Create the prompt for AI translation by loading it from prompts.txt and inserting content."""
    base = load_translation_prompt_from_txt()
    if not base:
        base = "Please translate the following content to {target_language} while preserving formatting.\n\n{content}"
    
    return base.replace("{target_language}", target_language).replace("{content}", content)

def translate_content_with_ai(content, target_language, ai_choice):
    """Translate content using the shared AI handler"""
    try:
        ai_handler = create_ai_handler(ai_choice)
        prompt = get_ai_translation_prompt(content, target_language)
        translated_content = ai_handler.get_response(prompt)
        return translated_content
    except Exception as e:
        logging.error(f"❌ Error with AI translation: {e}")
        return None

def get_full_model_name(ai_choice):
    """Get the full model name from environment variables"""
    if ai_choice in ['claude', 'anthropic']:
        return os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    elif ai_choice == 'openai':
        return os.getenv('OPENAI_MODEL', 'gpt-5')
    else:  # gemini
        return os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

def get_timestamp_string():
    """Get a timestamp string suitable for filenames"""
    now = datetime.now()
    return now.strftime("%Y%m%d_%H%M%S")

def safe_language_name(language):
    """Convert language name to safe filename component"""
    # Remove special characters and replace spaces with underscores
    safe_name = re.sub(r'[^\w\-_]', '', language.replace(' ', '_'))
    return safe_name[:20]  # Limit length

def save_translated_content(original_file_path, translated_content, ai_model, target_language):
    """Save the translated content with _AITranslated and language suffix"""
    original_path = Path(original_file_path)
    # Get the full model name
    full_model_name = get_full_model_name(ai_model)
    # Clean the model name for filename (replace dots and dashes with underscores)
    safe_model_name = full_model_name.replace('.', '_').replace('-', '_')
    # Clean target language for filename
    safe_lang = safe_language_name(target_language)
    # Add timestamp
    timestamp = get_timestamp_string()
    translated_path = original_path.parent / f"{original_path.stem}_AITranslated_{safe_lang}_{safe_model_name}_{timestamp}.md"
    
    try:
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        logging.info(f"✅ Translated content saved to: {translated_path}")
        return translated_path
        
    except Exception as e:
        logging.error(f"❌ Error saving translated content: {e}")
        return None

class NotionTranslator:
    """Handler for translating Notion pages block by block"""
    
    def __init__(self, target_language, ai_model='gemini', max_blocks=None):
        """
        Initialize the translator
        
        Args:
            target_language (str): Target language for translation
            ai_model (str): AI model to use
            max_blocks (int): Maximum number of blocks to translate (None for unlimited)
        """
        self.target_language = target_language
        self.ai_model = ai_model
        self.max_blocks = max_blocks
        self.writer = NotionWriter()
        self.ai_handler = create_ai_handler(ai_model)
        
        logging.info(f"🌍 Translator initialized for {target_language} using {ai_model}")
        if max_blocks:
            logging.info(f"🔢 Limited to {max_blocks} blocks")
    
    def translate_page_blocks(self, page_id):
        """
        Translate page blocks one by one preserving formatting
        
        Args:
            page_id (str): Notion page ID
            
        Returns:
            dict: Results of translation operation
        """
        try:
            # Create a custom AI handler that validates translation responses
            validated_ai_handler = ValidatedTranslationAI(self.ai_handler, self.target_language)
            
            # Get translation instructions for block-level use  
            translation_prompt = get_block_level_translation_instructions(self.target_language)
            
            # Use custom translation-specific block update (removes short text limit)
            application_result = self._intelligent_translation_update(
                page_id, translation_prompt, validated_ai_handler
            )
            
            return {
                'success': application_result['success'],
                'target_language': self.target_language,
                'blocks_processed': application_result.get('blocks_processed', 0),
                'successful_updates': application_result.get('successful_updates', 0),
                'skipped_updates': application_result.get('skipped_updates', 0),
                'failed_updates': application_result.get('failed_updates', 0),
                'application_result': application_result
            }
            
        except Exception as e:
            logging.error(f"❌ Block translation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _intelligent_translation_update(self, page_id, enhancement_prompt, ai_handler):
        """
        Translation-specific block update that translates even short content
        Based on NotionWriter.intelligent_block_by_block_update but removes text length limits
        """
        try:
            # Get blocks with early stopping for efficiency
            all_blocks = self.writer._load_cached_blocks(page_id)
            
            if not all_blocks:
                # Fall back to API calls if no cached data
                logging.info("📡 No cached data available, falling back to API calls...")
                if self.max_blocks:
                    # Fetch limited blocks for efficiency (3x buffer for filtering)
                    all_blocks = self.writer._get_all_blocks_recursively(page_id, self.max_blocks * 3)
                else:
                    # Full fetch only if no limit specified
                    all_blocks = self.writer._get_all_blocks_recursively(page_id)
                
                if not all_blocks:
                    return {
                        'success': False,
                        'message': 'No blocks found (cached or API)',
                        'blocks_updated': 0
                    }
            else:
                logging.info("🗂️ Using cached block data (much faster!)")
            
            # Find updatable blocks (STRICT synced block protection!)
            # But limit early to avoid unnecessary processing
            updatable_blocks = []
            synced_blocks_found = 0
            fetch_limit = self.max_blocks * 2 if self.max_blocks else None  # Fetch 2x requested to account for skipped blocks
            
            for i, block in enumerate(all_blocks):
                # Early termination if we've found enough candidates
                if fetch_limit and len(updatable_blocks) >= fetch_limit:
                    logging.info(f"🔢 Found {len(updatable_blocks)} candidates (2x requested limit), stopping search")
                    break
                    
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
                if self.writer._is_block_in_synced_content(block, all_blocks):
                    logging.warning(f"🚫 PROTECTED: Skipping block {block_id[:8]}... (inside synced content)")
                    continue
                    
                if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                                  'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'toggle', 'to_do',
                                  'image', 'video', 'file', 'pdf', 'audio', 'bookmark']:
                    text_content = self.writer._extract_plain_text_from_block(block)
                    # TRANSLATION DIFFERENCE: Accept ANY text content (no minimum length)
                    if text_content and len(text_content.strip()) > 0:
                        updatable_blocks.append(block)
            
            logging.info(f"🚫 Protected {synced_blocks_found} synced blocks from modification")
            
            # Now limit to actual requested amount
            if self.max_blocks and len(updatable_blocks) > self.max_blocks:
                original_count = len(updatable_blocks)
                updatable_blocks = updatable_blocks[:self.max_blocks]
                logging.info(f"🔢 Limited to first {self.max_blocks} blocks (found {original_count} candidates)")
            
            logging.info(f"📝 Processing {len(updatable_blocks)} blocks for translation")
            
            successful_updates = 0
            skipped_updates = 0
            failed_updates = 0
            
            # Process blocks one by one with AI and context tracking
            block_context = []
            
            for i, block in enumerate(updatable_blocks):
                try:
                    logging.info(f"🔄 Translating block {i+1}/{len(updatable_blocks)}: {block.get('type')}")
                    
                    result = self.writer.intelligent_block_update_with_context(
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
                            logging.info(f"✅ Translated block successfully")
                            
                            # Add to context for next blocks
                            original_text = self.writer._extract_plain_text_from_block(block)
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
                        logging.warning(f"❌ Block translation failed: {result.get('error', 'Unknown')}")
                        
                    # Gentle rate limit to respect API
                    import time
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
            logging.error(f"❌ Translation block update failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_updated': 0
            }

class ValidatedTranslationAI:
    """Wrapper for AI handler that validates translation responses"""
    
    def __init__(self, ai_handler, target_language):
        self.ai_handler = ai_handler
        self.target_language = target_language
        self.model_type = ai_handler.model_type
    
    def get_response(self, prompt, max_tokens=None, temperature=None):
        """Get response with translation validation"""
        # Extract the actual content from the context-aware prompt
        # The prompt has format: "...CURRENT BLOCK:\nType: xyz\nContent: actual_text\n..."
        original_text = ""
        if "Content: " in prompt:
            # Extract text after "Content: " and before next newline
            content_start = prompt.find("Content: ") + len("Content: ")
            content_end = prompt.find("\n", content_start)
            if content_end == -1:
                content_end = len(prompt)
            original_text = prompt[content_start:content_end].strip()
        
        if not original_text:
            # Fallback: try to find text after the last colon
            original_text = prompt.split(":")[-1].strip() if ":" in prompt else prompt[:50]
        
        # Get AI response
        response = self.ai_handler.get_response(prompt, max_tokens, temperature)
        
        if not response:
            return None
        
        # Validate the response (but be more lenient for very short original text)
        is_valid, cleaned_response = validate_translation_response(response, original_text, self.target_language)
        
        if not is_valid:
            logging.error(f"❌ Translation validation failed for text: '{original_text[:50]}'")
            logging.error(f"❌ AI response was: '{response[:100]}'")
            # For very short original text, be more lenient
            if len(original_text.strip()) < 5:
                logging.warning("🔄 Accepting response for very short text despite validation failure")
                return response
            return None
        
        return cleaned_response

def main():
    """Main function to orchestrate the AI translation process"""
    logging.info("🚀 Starting AI Translation...")
    
    # Get page ID, AI choice, target language, and block limit
    page_id, ai_choice, target_language, max_blocks = get_page_id_and_language()
    logging.info(f"📄 Processing page ID: {page_id}")
    logging.info(f"🤖 Using AI model: {ai_choice}")
    logging.info(f"🌍 Target language: {target_language}")
    if max_blocks:
        logging.info(f"🔢 Block limit: {max_blocks}")
    
    # Create AI handler for validation
    ai_handler = create_ai_handler(ai_choice)
    
    logging.info(f"✅ Target language accepted: {target_language}")
    
    # Option 1: Create a file-based translation (if markdown file exists)
    markdown_file = find_markdown_file(page_id)
    if markdown_file:
        logging.info("📄 Found existing markdown file, creating file-based translation...")
        content = read_markdown_content(markdown_file)
        if content:
            # Translate with AI and save to file
            translated_content = translate_content_with_ai(content, target_language, ai_choice)
            if translated_content:
                output_file = save_translated_content(markdown_file, translated_content, ai_choice, target_language)
                if output_file:
                    logging.info("🎉 File-based AI Translation completed successfully!")
                    logging.info(f"📁 Original file: {markdown_file}")
                    logging.info(f"📁 Translated file: {output_file}")
    else:
        logging.info("📄 No cached markdown file found - will only do live page translation")
    
    # Option 2: Direct Notion page translation (block by block)
    print("\nWould you like to also translate the live Notion page blocks? (y/n): ", end='')
    user_choice = input().strip().lower()
    
    if user_choice in ['y', 'yes']:
        logging.info("🔄 Starting block-by-block Notion page translation...")
        
        # Initialize translator with block limit
        translator = NotionTranslator(target_language, ai_choice, max_blocks)
        
        # Translate page blocks
        translation_result = translator.translate_page_blocks(page_id)
        
        if translation_result['success']:
            logging.info("🎉 Block-by-block translation completed successfully!")
            logging.info(f"📊 Processed {translation_result['blocks_processed']} blocks")
            logging.info(f"✅ Successful translations: {translation_result['successful_updates']}")
            logging.info(f"⏭️ Skipped blocks: {translation_result['skipped_updates']}")
            if translation_result['failed_updates'] > 0:
                logging.warning(f"❌ Failed translations: {translation_result['failed_updates']}")
        else:
            logging.error("❌ Block-by-block translation failed")
            error = translation_result.get('error', 'Unknown error')
            logging.error(f"❌ Error: {error}")
            sys.exit(1)
    else:
        logging.info("👍 Skipped live page translation - file translation completed")

if __name__ == "__main__":
    main()