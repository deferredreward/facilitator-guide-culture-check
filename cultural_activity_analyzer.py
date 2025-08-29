#!/usr/bin/env python3
"""
Cultural Activity Analyzer for Notion Pages

This script takes a Notion page ID, finds the corresponding markdown file,
and sends it to an AI model to analyze the cultural appropriateness of activities
and provide feedback for different regions of the world.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from ai_handler import create_ai_handler

# Add utils directory to path for utility imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from markdown_utils import clean_markdown_content
from file_finder import find_markdown_file_by_page_id

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def get_page_id():
    """Get page ID from command line arguments or prompt user"""
    parser = argparse.ArgumentParser(description='Analyze cultural appropriateness of activities in Notion pages')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    parser.add_argument('--ai', choices=['claude', 'anthropic', 'gemini', 'openai'], default='gemini',
                       help='AI model to use (default: gemini)')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to analyze for cultural activity feedback:")
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

def load_prompt_from_file(path: str = "prompts.txt", section: str = "Culture") -> str:
    """
    Load a prompt from prompts.txt by section name
    
    Args:
        path (str): Path to prompts file
        section (str): Section name (Reading, Translation, Culture, etc.)
        
    Returns:
        str: The prompt text
    """
    try:
        from pathlib import Path
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        
        # Find the section
        start_marker = f"# {section}:"
        start_idx = text.find(start_marker)
        if start_idx == -1:
            raise ValueError(f"Section '{section}' not found in {path}")
            
        section_text = text[start_idx:]
        
        # Find the first triple quote after the section header
        q1 = section_text.find('"""')
        if q1 == -1:
            raise ValueError(f"No triple-quoted prompt found in section '{section}'")
            
        q2 = section_text.find('"""', q1 + 3)
        if q2 == -1:
            raise ValueError(f"Unclosed triple-quoted prompt in section '{section}'")
            
        return section_text[q1 + 3:q2].strip()
        
    except Exception as e:
        # Fallback to a basic prompt if loading fails
        print(f"Warning: Failed to load prompt from {path}: {e}")
        return "You are an expert in cross-cultural communication and educational activity design. Provide detailed cultural analysis for the given content."

def get_cultural_analysis_prompt(content):
    """Create the prompt for cultural activity analysis"""
    # Load prompt template from prompts.txt
    prompt_template = load_prompt_from_file("prompts.txt", "Culture")
    
    # Replace {content} placeholder with actual content
    prompt = prompt_template.replace('{content}', content)
    
    return prompt

def analyze_content_with_ai(content, ai_choice):
    """Analyze content using the shared AI handler"""
    try:
        ai_handler = create_ai_handler(ai_choice)
        prompt = get_cultural_analysis_prompt(content)
        analysis_content = ai_handler.get_response(prompt, max_tokens=6000, temperature=0.4)
        return analysis_content
    except Exception as e:
        logging.error(f"❌ Error with AI analysis: {e}")
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

def save_analysis_content(original_file_path, analysis_content, ai_model):
    """Save the analysis content with _activity-feedback and AI model suffix"""
    original_path = Path(original_file_path)
    # Get the full model name
    full_model_name = get_full_model_name(ai_model)
    # Clean the model name for filename (replace dots and dashes with underscores)
    safe_model_name = full_model_name.replace('.', '_').replace('-', '_')
    # Add timestamp
    timestamp = get_timestamp_string()
    analysis_path = original_path.parent / f"{original_path.stem}_activity-feedback_{safe_model_name}_{timestamp}.md"
    
    try:
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write(analysis_content)
        
        logging.info(f"✅ Cultural analysis saved to: {analysis_path}")
        return analysis_path
        
    except Exception as e:
        logging.error(f"❌ Error saving analysis content: {e}")
        return None

def main():
    """Main function to orchestrate the cultural analysis process"""
    logging.info("🌍 Starting Cultural Activity Analysis...")
    
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
    
    # Analyze with AI
    analysis_content = analyze_content_with_ai(content, ai_choice)
    if not analysis_content:
        logging.error("❌ Failed to get AI analysis")
        sys.exit(1)
    
    # Save the analysis content
    output_file = save_analysis_content(markdown_file, analysis_content, ai_choice)
    if not output_file:
        sys.exit(1)
    
    logging.info("🎉 Cultural Activity Analysis completed successfully!")
    logging.info(f"📁 Original file: {markdown_file}")
    logging.info(f"📁 Analysis file: {output_file}")

if __name__ == "__main__":
    main() 