#!/usr/bin/env python3
"""
AI Reading Enhancer for Notion Pages

This script takes a Notion page ID, finds the corresponding markdown file,
and sends it to an AI model (Claude or Gemini) to improve readability
for non-native English speakers with 8th-grade education level.
"""

import os
import sys
import argparse
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from ai_handler import create_ai_handler
from markdown_utils import clean_markdown_content
from file_finder import find_markdown_file_by_page_id

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def get_page_id():
    """Get page ID from command line arguments or prompt user"""
    parser = argparse.ArgumentParser(description='Enhance Notion page readability using AI')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    parser.add_argument('--ai', choices=['claude', 'anthropic', 'gemini', 'openai'], default='gemini',
                       help='AI model to use (default: gemini)')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to enhance:")
        page_id = input().strip()
        
        if not page_id:
            logging.error("❌ No page ID provided")
            sys.exit(1)
    
    return page_id, args.ai

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

def get_ai_enhancement_prompt(content):
    """Create the prompt for AI readability enhancement (edit in place, no curly brackets)"""
    prompt = f"""You are an expert in making technical and educational content more accessible to non-native English speakers who have an 8th-grade education level.

Please directly edit and improve the following markdown content to make it easier to understand for someone whose English is their 2nd, 3rd, or 4th language. Edit the text in place, do not use curly brackets or any other markers for suggestions—just make the changes directly.

IMPORTANT GUIDELINES:
1. DO NOT change key terms, especially single terms on bullet point lines
2. DO NOT change technical terms that are essential to the content
3. DO NOT change proper nouns, names, or specific terminology
4. Edit the main body content directly, making it more readable and accessible
5. Focus on:
   - Simplifying complex sentence structures
   - Using shorter, clearer sentences
   - Replacing difficult words with simpler alternatives
   - Adding clarifying phrases where needed
   - Making instructions more step-by-step
   - Using active voice instead of passive voice

Here's the content to enhance:

{content}

Please return the improved content, keeping the original markdown formatting intact."""
    
    return prompt

def enhance_content_with_ai(content, ai_choice):
    """Enhance content using the shared AI handler"""
    try:
        ai_handler = create_ai_handler(ai_choice)
        prompt = get_ai_enhancement_prompt(content)
        enhanced_content = ai_handler.get_response(prompt)
        return enhanced_content
    except Exception as e:
        logging.error(f"❌ Error with AI enhancement: {e}")
        return None

def get_full_model_name(ai_choice):
    """Get the full model name from environment variables"""
    if ai_choice in ['claude', 'anthropic']:
        return os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    elif ai_choice == 'openai':
        return os.getenv('OPENAI_MODEL', 'gpt-4o')
    else:  # gemini
        return os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

def save_enhanced_content(original_file_path, enhanced_content, ai_model):
    """Save the enhanced content with _AIreading and AI model suffix"""
    original_path = Path(original_file_path)
    # Get the full model name
    full_model_name = get_full_model_name(ai_model)
    # Clean the model name for filename (replace dots and dashes with underscores)
    safe_model_name = full_model_name.replace('.', '_').replace('-', '_')
    enhanced_path = original_path.parent / f"{original_path.stem}_AIreading_{safe_model_name}.md"
    
    try:
        with open(enhanced_path, 'w', encoding='utf-8') as f:
            f.write(enhanced_content)
        
        logging.info(f"✅ Enhanced content saved to: {enhanced_path}")
        return enhanced_path
        
    except Exception as e:
        logging.error(f"❌ Error saving enhanced content: {e}")
        return None

def main():
    """Main function to orchestrate the AI enhancement process"""
    logging.info("🚀 Starting AI Reading Enhancement...")
    
    # Get page ID and AI choice
    page_id, ai_choice = get_page_id()
    logging.info(f"📄 Processing page ID: {page_id}")
    logging.info(f"🤖 Using AI model: {ai_choice}")
    
    # Find the markdown file
    markdown_file = find_markdown_file(page_id)
    if not markdown_file:
        sys.exit(1)
    
    # Read the content
    content = read_markdown_content(markdown_file)
    if not content:
        sys.exit(1)
    
    # Enhance with AI
    enhanced_content = enhance_content_with_ai(content, ai_choice)
    if not enhanced_content:
        logging.error("❌ Failed to get AI enhancement")
        sys.exit(1)
    
    # Save the enhanced content
    output_file = save_enhanced_content(markdown_file, enhanced_content, ai_choice)
    if not output_file:
        sys.exit(1)
    
    logging.info("🎉 AI Reading Enhancement completed successfully!")
    logging.info(f"📁 Original file: {markdown_file}")
    logging.info(f"📁 Enhanced file: {output_file}")

if __name__ == "__main__":
    main() 