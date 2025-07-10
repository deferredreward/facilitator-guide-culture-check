#!/usr/bin/env python3
"""
AI Question Generator for Trainer Evaluation

This script takes a Notion page ID, finds the corresponding markdown file,
and sends it to an AI model (Claude or Gemini) to generate two sets of questions:
1. Pre-training assessment questions to determine training needs
2. Post-training evaluation questions to assess learning outcomes
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
    parser = argparse.ArgumentParser(description='Generate trainer evaluation questions using AI')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    parser.add_argument('--ai', choices=['claude', 'anthropic', 'gemini', 'openai'], default='gemini',
                       help='AI model to use (default: gemini)')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to generate questions for:")
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

def load_trainer_questions_prompt():
    """Load the trainer questions prompt from prompts.txt"""
    try:
        with open('prompts.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the trainer questions prompt section
        start_marker = "# Trainer Questions:"
        end_marker = "# Culture:"
        
        start_idx = content.find(start_marker)
        if start_idx == -1:
            raise ValueError("Trainer Questions prompt not found in prompts.txt")
        
        end_idx = content.find(end_marker, start_idx)
        if end_idx == -1:
            # If no next section found, take until end of file
            trainer_section = content[start_idx:]
        else:
            trainer_section = content[start_idx:end_idx]
        
        # Extract just the prompt part (remove the header and leading whitespace)
        lines = trainer_section.split('\n')
        prompt_lines = []
        found_prompt_start = False
        
        for line in lines:
            if 'prompt = f"""' in line:
                found_prompt_start = True
                # Get the part after the f"""
                prompt_start = line.split('prompt = f"""')[1]
                if prompt_start:
                    prompt_lines.append(prompt_start)
            elif found_prompt_start:
                if line.strip().endswith('"""'):
                    # End of prompt, remove the closing quotes
                    prompt_lines.append(line.rstrip()[:-3])
                    break
                else:
                    prompt_lines.append(line)
        
        if not prompt_lines:
            raise ValueError("Could not parse trainer questions prompt from prompts.txt")
        
        # Join the lines and clean up indentation
        prompt_template = '\n'.join(prompt_lines)
        # Remove leading whitespace from each line consistently
        cleaned_lines = []
        for line in prompt_template.split('\n'):
            if line.strip():  # Non-empty lines
                # Remove up to 4 leading spaces
                if line.startswith('    '):
                    cleaned_lines.append(line[4:])
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append('')  # Preserve empty lines
        
        return '\n'.join(cleaned_lines)
        
    except Exception as e:
        logging.error(f"❌ Error loading trainer questions prompt: {e}")
        return None

def get_question_generation_prompt(content):
    """Create the prompt for AI question generation using the template from prompts.txt"""
    prompt_template = load_trainer_questions_prompt()
    if not prompt_template:
        raise ValueError("Failed to load trainer questions prompt from prompts.txt")
    
    # Replace the {content} placeholder with actual content
    prompt = prompt_template.format(content=content)
    return prompt

def generate_questions_with_ai(content, ai_choice):
    """Generate questions using the shared AI handler"""
    try:
        ai_handler = create_ai_handler(ai_choice)
        prompt = get_question_generation_prompt(content)
        questions = ai_handler.get_response(prompt)
        return questions
    except Exception as e:
        logging.error(f"❌ Error with AI question generation: {e}")
        return None

def get_full_model_name(ai_choice):
    """Get the full model name from environment variables"""
    if ai_choice in ['claude', 'anthropic']:
        return os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    elif ai_choice == 'openai':
        return os.getenv('OPENAI_MODEL', 'gpt-4o')
    else:  # gemini
        return os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')

def save_questions(original_file_path, questions, ai_model):
    """Save the generated questions with _TrainerQuestions and AI model suffix"""
    original_path = Path(original_file_path)
    # Get the full model name
    full_model_name = get_full_model_name(ai_model)
    # Clean the model name for filename (replace dots and dashes with underscores)
    safe_model_name = full_model_name.replace('.', '_').replace('-', '_')
    questions_path = original_path.parent / f"{original_path.stem}_TrainerQuestions_{safe_model_name}.md"
    
    try:
        with open(questions_path, 'w', encoding='utf-8') as f:
            f.write(questions)
        
        logging.info(f"✅ Generated questions saved to: {questions_path}")
        return questions_path
        
    except Exception as e:
        logging.error(f"❌ Error saving questions: {e}")
        return None

def main():
    """Main function to orchestrate the AI question generation process"""
    logging.info("🚀 Starting AI Question Generation...")
    
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
    
    # Generate questions with AI
    questions = generate_questions_with_ai(content, ai_choice)
    if not questions:
        logging.error("❌ Failed to generate questions")
        sys.exit(1)
    
    # Save the questions
    output_file = save_questions(markdown_file, questions, ai_choice)
    if not output_file:
        sys.exit(1)
    
    logging.info("🎉 AI Question Generation completed successfully!")
    logging.info(f"📁 Original file: {markdown_file}")
    logging.info(f"📁 Questions file: {output_file}")

if __name__ == "__main__":
    main() 