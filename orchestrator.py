#!/usr/bin/env python3
"""
Orchestrator Script - Complete AI Enhancement Workflow

This script orchestrates the full workflow:
1. Scrape Notion page
2. Generate trainer evaluation questions -> Insert near bottom as "Trainer Evaluation Questions"
3. Generate cultural adaptations -> Insert toggle blocks after activities
4. Enhance readability -> Replace page content with simplified version

Usage:
    python orchestrator.py <page_id> --ai <model_type>
    python orchestrator.py <page_id> --ai claude --dry-run
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Import existing modules
from notion_scraper import test_notion_api
from ai_question_generator import generate_questions_with_ai, find_markdown_file, read_markdown_content
from cultural_activity_analyzer import analyze_content_with_ai
from ai_reading_enhancer import enhance_content_with_ai, get_block_level_reading_instructions
from notion_writer import NotionWriter
from ai_handler import AIHandler
from file_finder import find_debug_file_by_page_id_only

# Setup logging with file output
def setup_dual_logging():
    """Setup dual logging: program operations + AI interactions"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    program_log_file = log_dir / f"orchestrator_{timestamp}_program.log"
    ai_log_file = log_dir / f"orchestrator_{timestamp}_ai_interactions.log"
    
    # Configure main program logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(program_log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create separate AI interaction logger
    ai_logger = logging.getLogger('ai_interactions')
    ai_logger.setLevel(logging.INFO)
    # Prevent propagation to avoid duplicate messages
    ai_logger.propagate = False
    ai_file_handler = logging.FileHandler(ai_log_file, encoding='utf-8')
    ai_file_handler.setFormatter(logging.Formatter('%(asctime)s - AI - %(message)s'))
    ai_logger.addHandler(ai_file_handler)
    # Force flush
    ai_file_handler.flush()
    
    logging.info(f"📝 Program logging: {program_log_file}")
    logging.info(f"🤖 AI interaction logging: {ai_log_file}")
    
    # Test AI logging immediately
    ai_logger.info("AI interaction logging system initialized")
    ai_file_handler.flush()
    
    return program_log_file, ai_log_file

# Setup dual logging
program_log_file, ai_log_file = setup_dual_logging()

# AI interaction logger
ai_logger = logging.getLogger('ai_interactions')

def extract_page_id_from_url(url_or_id):
    """
    Extract Notion page ID from URL or return ID if already clean
    
    Args:
        url_or_id (str): Notion URL or page ID
        
    Returns:
        str: Clean page ID
    """
    # If it's already a clean ID (32 chars, alphanumeric), return as-is
    if len(url_or_id) == 32 and url_or_id.replace('-', '').isalnum():
        return url_or_id
    
    # Extract from URL patterns
    import re
    
    # Pattern for URLs like: https://www.notion.so/unfoldingword/Form-Meaning-FG-Benjamin-Test-api-24772d5af2de800ebbddc5d44e5a33b9
    url_pattern = r'([a-f0-9]{32})$'
    match = re.search(url_pattern, url_or_id.replace('-', ''))
    
    if match:
        return match.group(1)
    
    # Pattern for URLs with dashes: extract last part
    if 'notion.so' in url_or_id:
        parts = url_or_id.split('-')
        if parts:
            last_part = parts[-1]
            # Remove any query parameters
            last_part = last_part.split('?')[0]
            if len(last_part) == 32 and last_part.isalnum():
                return last_part
    
    # If we can't extract, return as-is and let the API handle it
    return url_or_id.strip()

def log_ai_interaction(prompt, response, model_type, operation):
    """Log AI interactions separately"""
    try:
        ai_logger = logging.getLogger('ai_interactions')
        ai_logger.info(f"=== {operation.upper()} ===")
        ai_logger.info(f"Model: {model_type}")
        ai_logger.info(f"Prompt (first 200 chars): {prompt[:200]}...")
        ai_logger.info(f"Response (first 500 chars): {response[:500]}...")
        ai_logger.info(f"Full response length: {len(response)} characters")
        ai_logger.info("=" * 60)
        # Also log to main logger for now
        logging.info(f"AI Interaction logged: {operation} with {model_type}")
    except Exception as e:
        logging.error(f"Failed to log AI interaction: {e}")

def load_reading_prompt_from_txt(path: str = "prompts.txt") -> str:
    """Extract the Reading prompt from prompts.txt and adapt it for block-level use.

    We load the triple-quoted string under the '# Reading:' section and remove
    the '{content}' placeholder block, since the block content is injected elsewhere.
    """
    try:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
    except Exception:
        # Fallback to a minimal safe prompt
        return (
            "You are an expert in making technical and educational content more accessible "
            "to non-native English speakers at an 8th-grade level. Improve clarity and readability "
            "without changing technical terms or key nouns. Use shorter sentences and active voice."
        )

    # Locate the Reading section
    start_idx = text.find("# Reading:")
    if start_idx == -1:
        return (
            "You are an expert in making technical and educational content more accessible "
            "to non-native English speakers at an 8th-grade level. Improve clarity and readability "
            "without changing technical terms or key nouns. Use shorter sentences and active voice."
        )

    section = text[start_idx:]
    # Find the first triple quote after the section header
    q1 = section.find('"""')
    if q1 == -1:
        return (
            "You are an expert in making technical and educational content more accessible "
            "to non-native English speakers at an 8th-grade level. Improve clarity and readability "
            "without changing technical terms or key nouns. Use shorter sentences and active voice."
        )
    q2 = section.find('"""', q1 + 3)
    if q2 == -1:
        return (
            "You are an expert in making technical and educational content more accessible "
            "to non-native English speakers at an 8th-grade level. Improve clarity and readability "
            "without changing technical terms or key nouns. Use shorter sentences and active voice."
        )
    extracted = section[q1 + 3:q2]

    # Remove the '{content}' insertion block and its header line
    import re
    extracted = re.sub(
        r"(?ms)^\s*Here\'s the content to enhance:\s*\n\s*\{content\}\s*\n",
        "",
        extracted,
    )
    return extracted.strip()

class NotionOrchestrator:
    """Orchestrates the complete AI enhancement workflow"""
    
    def __init__(self, ai_model='claude', dry_run=False):
        """
        Initialize orchestrator
        
        Args:
            ai_model (str): AI model to use ('claude', 'gemini', 'openai')
            dry_run (bool): If True, show what would be done without making changes
        """
        self.ai_model = ai_model
        self.dry_run = dry_run
        self.writer = NotionWriter()
        self.ai_handler = AIHandler(ai_model)
        
        logging.info(f"🚀 Orchestrator initialized with AI model: {ai_model}")
        if dry_run:
            logging.info("🔍 DRY RUN MODE - No actual changes will be made")
    
    def run_complete_workflow(self, page_id):
        """
        Run the complete AI enhancement workflow
        
        Args:
            page_id (str): Notion page ID
            
        Returns:
            dict: Results of the complete workflow
        """
        workflow_results = {
            'page_id': page_id,
            'ai_model': self.ai_model,
            'dry_run': self.dry_run,
            'timestamp': datetime.now().isoformat(),
            'steps': {}
        }
        
        try:
            # Step 1: Scrape the page
            logging.info("📡 Step 1: Scraping Notion page...")
            scrape_result = self._scrape_page(page_id)
            workflow_results['steps']['scrape'] = scrape_result
            
            if not scrape_result['success']:
                return workflow_results
            
            # Step 2: Generate trainer questions and insert
            logging.info("❓ Step 2: Generating trainer evaluation questions...")
            questions_result = self._generate_and_insert_questions(page_id)
            workflow_results['steps']['questions'] = questions_result
            
            # Step 3: Generate cultural adaptations and insert
            logging.info("🌍 Step 3: Generating cultural adaptations...")
            culture_result = self._generate_and_insert_cultural_adaptations(page_id)
            workflow_results['steps']['culture'] = culture_result
            
            # Step 4: Enhance readability (do this last as it modifies content)
            logging.info("📚 Step 4: Enhancing readability...")
            reading_result = self._enhance_readability(page_id)
            workflow_results['steps']['reading'] = reading_result
            
            # Overall success
            # Consider success only if reading step updated any blocks or culture inserted any blocks
            reading = workflow_results['steps'].get('reading', {})
            culture = workflow_results['steps'].get('culture', {})
            any_updates = (reading.get('successful_updates', 0) > 0) or (culture.get('adaptations_added', 0) > 0)
            all_steps_ok = all(result.get('success', False) for result in workflow_results['steps'].values())
            workflow_results['success'] = all_steps_ok and any_updates
            if not any_updates:
                logging.warning("⚠️ No updates were applied (0 successful updates, 0 cultural insertions)")
            
            logging.info(f"✅ Workflow completed. Overall success: {workflow_results['success']}")
            return workflow_results
            
        except Exception as e:
            logging.error(f"❌ Workflow failed: {e}")
            workflow_results['success'] = False
            workflow_results['error'] = str(e)
            return workflow_results
    
    def _scrape_page(self, page_id):
        """Scrape the Notion page"""
        try:
            result = test_notion_api(page_id)
            return {
                'success': result,
                'message': 'Page scraped successfully' if result else 'Scraping failed',
                'cached_data': result
            }
        except Exception as e:
            logging.error(f"❌ Scraping failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_and_insert_questions(self, page_id):
        """Generate trainer questions and insert them"""
        try:
            # Find and read markdown file
            markdown_file = find_markdown_file(page_id)
            if not markdown_file:
                return {
                    'success': False,
                    'error': 'No markdown file found for page'
                }
            
            content = read_markdown_content(markdown_file)
            if not content:
                return {
                    'success': False,
                    'error': 'Failed to read markdown content'
                }
            
            # Generate questions
            questions_content = generate_questions_with_ai(content, self.ai_model)
            
            if not questions_content:
                return {
                    'success': False,
                    'error': 'Failed to generate questions'
                }
            
            # Find insertion point - look for existing "Trainer Evaluation Questions" or insert at end
            insertion_result = self._insert_trainer_questions(page_id, questions_content)
            
            return {
                'success': insertion_result['success'],
                'content_generated': bool(questions_content),
                'insertion_result': insertion_result
            }
            
        except Exception as e:
            logging.error(f"❌ Questions generation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_and_insert_cultural_adaptations(self, page_id):
        """Generate cultural adaptations and insert them in activity toggle blocks"""
        try:
            if self.dry_run:
                logging.info("🔍 DRY RUN: Would find activity toggles and add cultural adaptations")
                return {
                    'success': True,
                    'content_generated': True,
                    'insertion_result': {'success': True, 'message': 'DRY RUN', 'blocks_added': 0}
                }
            
            # Build activity sections (toggles and headings)
            sections = self.writer.find_activity_sections(page_id)
            if not sections:
                # Fallback to page-level cultural analysis and append at end
                logging.warning("⚠️ No specific activity sections found; computing page-level cultural analysis")
                markdown_file = find_markdown_file(page_id)
                if not markdown_file:
                    return {'success': False, 'error': 'No markdown file for fallback'}
                content = read_markdown_content(markdown_file)
                if not content:
                    return {'success': False, 'error': 'Failed to read markdown for fallback'}
                cultural_content = analyze_content_with_ai(content, self.ai_model)
                if not cultural_content:
                    return {'success': False, 'error': 'Cultural analysis failed'}
                insertion_result = self._insert_cultural_adaptations(page_id, cultural_content)
                return {
                    'success': insertion_result['success'],
                    'content_generated': True,
                    'insertion_result': insertion_result
                }
            
            total_added = 0
            for sec in sections:
                try:
                    if len(sec['content_text']) < 50:
                        continue
                    # Load cultural prompt template from prompts.txt (Culture section)
                    try:
                        txt = Path('prompts.txt').read_text(encoding='utf-8')
                        start = txt.find('# Culture:')
                        q1 = txt.find('"""', start)
                        q2 = txt.find('"""', q1 + 3) if q1 != -1 else -1
                        culture_template = txt[q1 + 3:q2] if q1 != -1 and q2 != -1 else None
                    except Exception:
                        culture_template = None
                    if not culture_template:
                        # Minimal fallback
                        culture_template = (
                            "Analyze the activity below for cultural appropriateness. Provide brief adaptations and alternatives.\n\n{content}"
                        )
                    prompt = culture_template.replace('{content}', sec['content_text'])
                    analysis = self.ai_handler.get_response(prompt, max_tokens=3000, temperature=0.4)
                    log_ai_interaction(prompt, analysis or '', self.ai_model, 'CULTURAL_ACTIVITY')
                    if not analysis:
                        continue
                    title = f"🌍 Cultural guidance for: {sec['label'][:60]}"
                    append_res = self.writer.append_cultural_toggle_to_container(
                        sec['container_id'], title, analysis, max_blocks=40
                    )
                    if append_res.get('success') and not append_res.get('skipped'):
                        total_added += 1
                except Exception as e:
                    logging.warning(f"⚠️ Failed to append cultural guidance: {e}")
            
            return {
                'success': total_added > 0,
                'content_generated': True,
                'adaptations_added': total_added,
                'insertion_result': {
                    'success': total_added > 0,
                    'message': f"Added {total_added} cultural guidance toggles",
                    'blocks_added': total_added
                }
            }
            
        except Exception as e:
            logging.error(f"❌ Cultural analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _enhance_readability(self, page_id):
        """Enhance readability using intelligent block-by-block AI updates"""
        try:
            if self.dry_run:
                logging.info("🔍 DRY RUN: Would perform intelligent block-by-block reading enhancement")
                return {
                    'success': True,
                    'content_generated': True,
                    'applied': False,
                    'blocks_updated': 0,
                    'message': 'DRY RUN: Would enhance readability intelligently'
                }
            
            # Use Reading prompt from prompts.txt (block-level instructions)
            enhancement_prompt = get_block_level_reading_instructions()
            
            application_result = self.writer.intelligent_block_by_block_update(
                page_id, enhancement_prompt, self.ai_handler
            )
            
            return {
                'success': application_result['success'],
                'content_generated': True,
                'applied': True,
                'blocks_processed': application_result.get('blocks_processed', 0),
                'successful_updates': application_result.get('successful_updates', 0),
                'skipped_updates': application_result.get('skipped_updates', 0),
                'failed_updates': application_result.get('failed_updates', 0),
                'application_result': application_result
            }
            
        except Exception as e:
            logging.error(f"❌ Reading enhancement failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _insert_trainer_questions(self, page_id, questions_content):
        """Insert trainer evaluation questions at the appropriate location"""
        try:
            if self.dry_run:
                logging.info("🔍 DRY RUN: Would insert trainer questions section")
                return {
                    'success': True,
                    'message': 'DRY RUN: Trainer questions would be inserted',
                    'blocks_added': 0
                }
            
            # Use the enhanced writer to insert questions
            result = self.writer.insert_trainer_questions_section(page_id, questions_content)
            
            if result['success']:
                logging.info(f"✅ Inserted {result['blocks_added']} blocks for trainer questions")
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _insert_cultural_adaptations(self, page_id, cultural_content):
        """Insert cultural adaptations after each activity"""
        try:
            if self.dry_run:
                logging.info("🔍 DRY RUN: Would insert cultural adaptations")
                return {
                    'success': True,
                    'message': 'DRY RUN: Cultural adaptations would be inserted',
                    'blocks_added': 0
                }
            
            # Use the enhanced writer to insert cultural adaptations
            result = self.writer.insert_cultural_adaptations_after_activities(page_id, cultural_content)
            
            if result['success']:
                logging.info(f"✅ Inserted {result['blocks_added']} blocks for cultural adaptations")
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _find_insertion_marker(self, page_id, marker_text):
        """
        Find blocks that contain specific marker text for intelligent insertion
        
        Args:
            page_id (str): Notion page ID
            marker_text (str): Text to search for as insertion marker
            
        Returns:
            list: Blocks that contain the marker text
        """
        def criteria_func(block):
            text_content = self.writer._extract_plain_text_from_block(block)
            return marker_text.lower() in text_content.lower() if text_content else False
        
        return self.writer.find_blocks_by_criteria(page_id, criteria_func)

def main():
    """Main function to run the orchestrator"""
    parser = argparse.ArgumentParser(description='Run complete AI enhancement workflow on Notion page')
    parser.add_argument('page_id', help='Notion page ID or URL')
    parser.add_argument('--ai', default='claude', choices=['claude', 'gemini', 'openai'],
                      help='AI model to use (default: claude)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without making changes')
    parser.add_argument('--only', choices=['scrape', 'questions', 'culture', 'reading'],
                      help='Run only a specific step instead of the full workflow')
    
    args = parser.parse_args()
    
    # Extract clean page ID from URL if needed
    clean_page_id = extract_page_id_from_url(args.page_id)
    logging.info(f"�� Input: {args.page_id}")
    logging.info(f"🎯 Extracted Page ID: {clean_page_id}")
    
    # Initialize orchestrator
    orchestrator = NotionOrchestrator(ai_model=args.ai, dry_run=args.dry_run)
    
    # Run single step if requested
    if args.only:
        step = args.only
        if step == 'scrape':
            res = orchestrator._scrape_page(clean_page_id)
        elif step == 'questions':
            res = orchestrator._generate_and_insert_questions(clean_page_id)
        elif step == 'culture':
            res = orchestrator._generate_and_insert_cultural_adaptations(clean_page_id)
        else:  # reading
            res = orchestrator._enhance_readability(clean_page_id)

        print("\n" + "="*60)
        print(f"🎯 STEP RESULT: {step.upper()}")
        print("="*60)
        status = "✅" if res.get('success') else "❌"
        print(f"Status: {status}")
        if 'message' in res:
            print(f"Message: {res['message']}")
        if step == 'culture':
            print(f"Adaptations added: {res.get('adaptations_added', 0)}")
        if step == 'reading':
            print(f"Successful updates: {res.get('successful_updates', 0)}")
        sys.exit(0 if res.get('success') else 1)

    # Run complete workflow
    results = orchestrator.run_complete_workflow(clean_page_id)
    
    # Print results summary
    print("\n" + "="*60)
    print("🎯 WORKFLOW RESULTS SUMMARY")
    print("="*60)
    print(f"Page ID: {results.get('page_id', 'N/A')}")
    print(f"AI Model: {results.get('ai_model', 'N/A')}")
    print(f"Dry Run: {results.get('dry_run', 'N/A')}")
    print(f"Overall Success: {results.get('success', False)}")
    print(f"Timestamp: {results.get('timestamp', 'N/A')}")
    
    print("\n📋 STEP RESULTS:")
    for step_name, step_result in results.get('steps', {}).items():
        status = "✅" if step_result.get('success') else "❌"
        print(f"{status} {step_name.title()}: {step_result.get('message', 'Completed')}")
    
    if not results.get('success', False):
        error_msg = results.get('error', 'Unknown error')
        print(f"\n❌ Workflow failed: {error_msg}")
        sys.exit(1)
    
    print("\n🎉 Workflow completed successfully!")

if __name__ == "__main__":
    main()