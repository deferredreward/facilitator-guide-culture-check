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
from dotenv import load_dotenv
from ai_handler import create_ai_handler
from markdown_utils import clean_markdown_content

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
    saved_pages_dir = Path("saved_pages")
    
    if not saved_pages_dir.exists():
        logging.error("❌ saved_pages directory not found")
        return None
    
    # Look for the markdown file
    markdown_file = saved_pages_dir / f"notion_page_{page_id}.md"
    
    if not markdown_file.exists():
        logging.error(f"❌ Markdown file not found: {markdown_file}")
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

def get_cultural_analysis_prompt(content):
    """Create the prompt for cultural activity analysis"""
    prompt = f"""You are an expert in cross-cultural communication and educational activities. You have deep knowledge of cultural sensitivities, communication styles, and learning preferences across different regions of the world.

Please analyze the following educational content and provide detailed feedback on the cultural appropriateness of the activities described. Focus on identifying where activities would work well and where they might face challenges in different cultural contexts.

ANALYSIS REQUIREMENTS:

1. **Activity Identification**: Identify all activities, exercises, and interactive elements in the content.

2. **Cultural Region Analysis**: For each activity, analyze its suitability for:
   - East Asia (China, Japan, Korea, etc.)
   - South Asia (India, Pakistan, Bangladesh, etc.)
   - Southeast Asia (Thailand, Vietnam, Indonesia, etc.)
   - Middle East & North Africa
   - Sub-Saharan Africa (or other regions of Africa with similar cultural contexts)
   - Latin America & Caribbean
   - Eastern Europe
   - Western Europe & North America
   - Pacific Islands
   - other unique cultural contexts

3. **Cultural Factors to Consider**:
   - Communication styles (direct vs. indirect)
   - Power distance and authority relationships
   - Individualism vs. collectivism
   - Gender roles and expectations
   - Religious and spiritual considerations
   - Educational traditions and preferences
   - Physical contact and personal space
   - Time orientation and scheduling
   - Group dynamics and social hierarchies
   - etc

4. **For Each Activity, Provide**:
   - **Where it would work well** and why
   - **Where it might face challenges** and specific reasons why
   - **Alternative activities** for regions where the original might not work well
   - **Cultural adaptations** that could make it more suitable (outline entire activity with new instructions)

5. **Format Your Response**:
   Use clear markdown formatting with:
   - Headers for each activity
   - Bullet points for regions and feedback
   - Clear explanations of cultural reasoning
   - Specific, actionable alternative suggestions

Here's the content to analyze:

{content}

Please provide a comprehensive cultural analysis that would help facilitators understand how to adapt these activities for different cultural contexts."""

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
        return os.getenv('OPENAI_MODEL', 'gpt-4o')
    else:  # gemini
        return os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

def save_analysis_content(original_file_path, analysis_content, ai_model):
    """Save the analysis content with _activity-feedback and AI model suffix"""
    original_path = Path(original_file_path)
    # Get the full model name
    full_model_name = get_full_model_name(ai_model)
    # Clean the model name for filename (replace dots and dashes with underscores)
    safe_model_name = full_model_name.replace('.', '_').replace('-', '_')
    analysis_path = original_path.parent / f"{original_path.stem}_activity-feedback_{safe_model_name}.md"
    
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