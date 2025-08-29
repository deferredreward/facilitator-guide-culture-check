#!/usr/bin/env python3
"""
Orchestrator Script - Complete AI Enhancement Workflow

This script orchestrates the full workflow:
1. Scrape Notion page
2. Enhance readability -> Replace page content with ESL-accessible simplified version
   - If --unsync-blocks flag is used, synced blocks are automatically converted to regular blocks during processing
3. Generate trainer evaluation questions -> Insert near bottom as "Trainer Evaluation Questions"
4. Generate cultural adaptations -> Insert toggle blocks after activities

Usage:
    python orchestrator.py <page_id> --ai <model_type>
    python orchestrator.py <page_id> --ai claude --dry-run
    python orchestrator.py <page_id> --unsync-blocks  # Convert synced blocks during AI processing
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
from ai_translator import NotionTranslator
from notion_writer import load_prompt_from_file
from notion_block_editor import test_whole_page_json_edit

# Import utilities from utils directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
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

def extract_page_id_from_text(text):
    """Extract page ID from various formats (URL, filename, etc.)"""
    text = text.strip()
    
    # If it's already just a page ID (32 hex chars with optional dashes)
    clean_id = text.replace('-', '')
    if len(clean_id) == 32 and all(c in '0123456789abcdef' for c in clean_id.lower()):
        return clean_id
    
    # Extract from filename format: "Something-FG-<page_id>"
    if '-' in text:
        parts = text.split('-')
        for part in reversed(parts):  # Check from end
            clean_part = part.replace('-', '')
            if len(clean_part) == 32 and all(c in '0123456789abcdef' for c in clean_part.lower()):
                return clean_part
    
    # Extract from URL format
    if 'notion.so' in text or 'notion.site' in text:
        # Find the page ID in the URL (32 hex chars)
        import re
        match = re.search(r'([a-f0-9]{32})', text.lower())
        if match:
            return match.group(1)
    
    return None

def extract_page_id_from_url(url_or_id):
    """
    Extract Notion page ID from URL or return ID if already clean
    
    Args:
        url_or_id (str): Notion URL or page ID
        
    Returns:
        str: Clean page ID
    """
    # Use the more robust extraction function
    extracted = extract_page_id_from_text(url_or_id)
    if extracted:
        return extracted
    
    # Fallback to original logic for backward compatibility
    if len(url_or_id) == 32 and url_or_id.replace('-', '').isalnum():
        return url_or_id
    
    return url_or_id.strip()

def log_ai_interaction(prompt, response, model_type, operation):
    """Log AI interactions separately"""
    try:
        # Handle None values gracefully
        prompt = prompt or ""
        response = response or ""
        model_type = model_type or "unknown"
        operation = operation or "unknown"
        
        ai_logger = logging.getLogger('ai_interactions')
        ai_logger.info(f"=== {operation.upper()} ===")
        ai_logger.info(f"Model: {model_type}")
        ai_logger.info(f"FULL PROMPT:\n{prompt}")
        ai_logger.info(f"FULL RESPONSE:\n{response}")
        ai_logger.info(f"Response length: {len(response)} characters")
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
    
    def __init__(self, reading_ai='claude', questions_ai='claude', culture_ai='claude', dry_run=False, num_blocks=None, unsync_blocks=False, notify_sms=False, notify_system=False):
        """
        Initialize orchestrator
        
        Args:
            reading_ai (str): AI model to use for reading level adaptation ('claude', 'gemini', 'openai', 'xai')
            questions_ai (str): AI model to use for trainer questions ('claude', 'gemini', 'openai', 'xai')
            culture_ai (str): AI model to use for cultural suggestions ('claude', 'gemini', 'openai', 'xai')
            dry_run (bool): If True, show what would be done without making changes
            num_blocks (int): Limit number of blocks to process (for testing)
            unsync_blocks (bool): If True, unsync synced blocks before processing
            notify_sms (bool): If True, send SMS notifications for page completion
            notify_system (bool): If True, send system notifications for page completion
        """
        self.reading_ai = reading_ai
        self.questions_ai = questions_ai
        self.culture_ai = culture_ai
        # Keep backward compatibility
        self.ai_model = reading_ai  # Default fallback
        self.dry_run = dry_run
        self.num_blocks = num_blocks
        self.unsync_blocks = unsync_blocks
        self.notify_sms = notify_sms
        self.notify_system = notify_system
        self.writer = NotionWriter()
        
        # Create AI handlers for each task
        self.reading_ai_handler = AIHandler(reading_ai)
        self.questions_ai_handler = AIHandler(questions_ai)
        self.culture_ai_handler = AIHandler(culture_ai)
        # Keep for backward compatibility
        self.ai_handler = self.reading_ai_handler
        
        logging.info(f"🚀 Orchestrator initialized with AI models:")
        logging.info(f"  📚 Reading: {reading_ai}")
        logging.info(f"  ❓ Questions: {questions_ai}")
        logging.info(f"  🌍 Culture: {culture_ai}")
        if dry_run:
            logging.info("🔍 DRY RUN MODE - No actual changes will be made")
    
    def _get_page_title(self, page_id):
        """Get the title of a page for notifications"""
        try:
            from utils.file_finder import find_debug_file_by_page_id_only
            import json
            
            # Try to get title from cached debug file first
            debug_file = find_debug_file_by_page_id_only(page_id)
            if debug_file:
                with open(debug_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    page_info = data.get('page', {})
                    properties = page_info.get('properties', {})
                    for prop_name, prop_data in properties.items():
                        if prop_data.get('type') == 'title':
                            title_array = prop_data.get('title', [])
                            if title_array:
                                return ''.join([t.get('text', {}).get('content', '') for t in title_array])
            
            # Fallback to page ID if we can't get title
            return f"Page {page_id[:8]}..."
        except Exception:
            return f"Page {page_id[:8]}..."
    
    def _send_notifications(self, page_id, page_title, success, current_page, total_pages, error_message=None):
        """Send notifications based on configuration"""
        if not self.notify_sms and not self.notify_system:
            return
        
        try:
            if self.notify_sms:
                from utils.notify import send_page_completion_notification
                send_page_completion_notification(
                    page_id=page_id,
                    page_title=page_title,
                    success=success,
                    ai_models={'reading': self.reading_ai, 'questions': self.questions_ai, 'culture': self.culture_ai},
                    current_page=current_page,
                    total_pages=total_pages,
                    error_message=error_message
                )
            
            if self.notify_system:
                from utils.notify import send_system_notification
                status = "✅ Completed" if success else "❌ Failed"
                progress = f"({current_page}/{total_pages})"
                title_short = page_title[:30] + "..." if len(page_title) > 30 else page_title
                send_system_notification(
                    title=f"FG Page {status} {progress}",
                    message=f"{title_short}"
                )
        except Exception as e:
            logging.warning(f"Notification failed: {e}")
    
    def _send_batch_notifications(self, total_pages, completed_pages, failed_pages):
        """Send batch completion notifications"""
        if not self.notify_sms and not self.notify_system:
            return
        
        try:
            if self.notify_sms:
                from utils.notify import send_batch_completion_notification
                send_batch_completion_notification(
                    total_pages=total_pages,
                    completed_pages=completed_pages,
                    failed_pages=failed_pages,
                    ai_models={'reading': self.reading_ai, 'questions': self.questions_ai, 'culture': self.culture_ai}
                )
            
            if self.notify_system:
                from utils.notify import send_system_notification
                if failed_pages == 0:
                    send_system_notification(
                        title=f"🎉 FG Batch Complete",
                        message=f"All {completed_pages} pages processed successfully!"
                    )
                else:
                    send_system_notification(
                        title=f"⚠️ FG Batch Complete",
                        message=f"{completed_pages} success, {failed_pages} failed"
                    )
        except Exception as e:
            logging.warning(f"Batch notification failed: {e}")
    
    def run_batch_workflow(self, page_ids):
        """
        Run the complete AI enhancement workflow on multiple pages
        
        Args:
            page_ids (list): List of Notion page IDs
            
        Returns:
            dict: Results of the batch workflow
        """
        batch_results = {
            'total_pages': len(page_ids),
            'completed_pages': 0,
            'failed_pages': 0,
            'page_results': [],
            'ai_models': {
                'reading': self.reading_ai,
                'questions': self.questions_ai,
                'culture': self.culture_ai
            },
            'dry_run': self.dry_run,
            'timestamp': datetime.now().isoformat()
        }
        
        logging.info(f"🚀 Starting batch processing of {len(page_ids)} pages...")
        
        for i, page_id in enumerate(page_ids, 1):
            page_title = self._get_page_title(page_id)
            logging.info(f"📄 Processing page {i}/{len(page_ids)}: {page_title} ({page_id[:8]}...)")
            
            try:
                page_result = self.run_complete_workflow(page_id)
                batch_results['page_results'].append(page_result)
                
                if page_result.get('success', False):
                    batch_results['completed_pages'] += 1
                    logging.info(f"✅ Page {i} completed successfully")
                    self._send_notifications(page_id, page_title, True, i, len(page_ids))
                else:
                    batch_results['failed_pages'] += 1
                    error_msg = page_result.get('error', 'Unknown error')
                    logging.error(f"❌ Page {i} failed: {error_msg}")
                    self._send_notifications(page_id, page_title, False, i, len(page_ids), error_msg)
                    
            except Exception as e:
                logging.error(f"❌ Page {i} failed with exception: {e}")
                batch_results['failed_pages'] += 1
                batch_results['page_results'].append({
                    'page_id': page_id,
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                self._send_notifications(page_id, page_title, False, i, len(page_ids), str(e))
        
        batch_results['overall_success'] = batch_results['failed_pages'] == 0
        logging.info(f"🎯 Batch processing completed: {batch_results['completed_pages']}/{batch_results['total_pages']} successful")
        
        # Send batch completion notification
        self._send_batch_notifications(
            total_pages=batch_results['total_pages'],
            completed_pages=batch_results['completed_pages'],
            failed_pages=batch_results['failed_pages']
        )
        
        return batch_results

    def _run_batch_single_step(self, page_ids, step, target_language=None):
        """
        Run a single step on multiple pages
        
        Args:
            page_ids (list): List of Notion page IDs
            step (str): Step to run ('scrape', 'questions', 'culture', 'reading', 'translation')
            target_language (str): Target language for translation (if step is 'translation')
            
        Returns:
            dict: Results of the batch single step
        """
        batch_results = {
            'total_pages': len(page_ids),
            'completed_pages': 0,
            'failed_pages': 0,
            'page_results': [],
            'step': step,
            'target_language': target_language,
            'ai_models': {
                'reading': self.reading_ai,
                'questions': self.questions_ai,
                'culture': self.culture_ai
            },
            'dry_run': self.dry_run,
            'timestamp': datetime.now().isoformat()
        }
        
        logging.info(f"🚀 Starting batch {step} processing of {len(page_ids)} pages...")
        
        for i, page_id in enumerate(page_ids, 1):
            page_title = self._get_page_title(page_id)
            logging.info(f"📄 Processing page {i}/{len(page_ids)}: {page_title} ({page_id[:8]}...)")
            
            try:
                # Run the specific step
                if step == 'scrape':
                    page_result = self._scrape_page(page_id)
                elif step == 'questions':
                    page_result = self._generate_and_insert_questions(page_id)
                elif step == 'culture':
                    page_result = self._generate_and_insert_cultural_adaptations(page_id)
                elif step == 'reading':
                    page_result = self._enhance_readability(page_id)
                elif step == 'translation':
                    page_result = self._translate_content(page_id, target_language)
                else:
                    raise ValueError(f"Unknown step: {step}")
                
                # Add page metadata to result
                page_result['page_id'] = page_id
                page_result['page_title'] = page_title
                page_result['timestamp'] = datetime.now().isoformat()
                
                batch_results['page_results'].append(page_result)
                
                if page_result.get('success', False):
                    batch_results['completed_pages'] += 1
                    logging.info(f"✅ Page {i} completed successfully")
                    self._send_notifications(page_id, page_title, True, i, len(page_ids))
                else:
                    batch_results['failed_pages'] += 1
                    error_msg = page_result.get('error', 'Unknown error')
                    logging.error(f"❌ Page {i} failed: {error_msg}")
                    self._send_notifications(page_id, page_title, False, i, len(page_ids), error_msg)
                    
            except Exception as e:
                logging.error(f"❌ Page {i} failed with exception: {e}")
                batch_results['failed_pages'] += 1
                batch_results['page_results'].append({
                    'page_id': page_id,
                    'page_title': page_title,
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                self._send_notifications(page_id, page_title, False, i, len(page_ids), str(e))
        
        batch_results['overall_success'] = batch_results['failed_pages'] == 0
        logging.info(f"🎯 Batch {step} processing completed: {batch_results['completed_pages']}/{batch_results['total_pages']} successful")
        
        # Send batch completion notification
        self._send_batch_notifications(
            total_pages=batch_results['total_pages'],
            completed_pages=batch_results['completed_pages'],
            failed_pages=batch_results['failed_pages']
        )
        
        return batch_results

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
            'ai_models': {
                'reading': self.reading_ai,
                'questions': self.questions_ai,
                'culture': self.culture_ai
            },
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
            
            # Note: Synced block conversion (if --unsync-blocks flag is used) 
            # happens automatically during AI processing, not as a separate step
            # Step 2: Enhance readability first (ESL English enhancement)
            logging.info("📚 Step 2: Enhancing readability for ESL accessibility...")
            reading_result = self._enhance_readability(page_id)
            workflow_results['steps']['reading'] = reading_result
            
            # Step 3: Generate trainer questions and insert
            logging.info("❓ Step 3: Generating trainer evaluation questions...")
            questions_result = self._generate_and_insert_questions(page_id)
            workflow_results['steps']['questions'] = questions_result
            
            # Step 4: Generate cultural adaptations and insert (do this last)
            logging.info("🌍 Step 4: Generating cultural adaptations...")
            culture_result = self._generate_and_insert_cultural_adaptations(page_id)
            workflow_results['steps']['culture'] = culture_result
            
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
    
    def _unsync_synced_blocks(self, page_id):
        """Unsync all synced blocks on the page"""
        try:
            result = self.writer.unsync_blocks_on_page(page_id, dry_run=self.dry_run)
            return {
                'success': result['success'],
                'message': result.get('message', 'Unsync operation completed'),
                'blocks_unsynced': result.get('blocks_unsynced', 0),
                'cancelled': result.get('cancelled', False),
                'errors': result.get('errors', [])
            }
        except Exception as e:
            logging.error(f"❌ Unsync failed: {e}")
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
            
            # Generate questions using questions-specific AI
            questions_content = generate_questions_with_ai(content, self.questions_ai)
            
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
                cultural_content = analyze_content_with_ai(content, self.culture_ai)
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
                    analysis = self.culture_ai_handler.get_response(prompt, max_tokens=3000, temperature=0.4)
                    log_ai_interaction(prompt, analysis or '', self.culture_ai, 'CULTURAL_ACTIVITY')
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
    
    def _get_cached_blocks(self, page_id):
        """Try to get cached blocks from recent scrape data"""
        try:
            # Try to load from cached debug file
            debug_file = find_debug_file_by_page_id_only(page_id)
            if debug_file:
                with open(debug_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'blocks' in data and isinstance(data['blocks'], list):
                        logging.info(f"✅ Loaded {len(data['blocks'])} blocks from cached data")
                        logging.info("🗂️ Using cached block data (much faster!)")
                        return data['blocks']
            
            logging.info("⚠️ No cached blocks found, will fetch fresh")
            return None
            
        except Exception as e:
            logging.warning(f"⚠️ Could not load cached blocks: {e}")
            return None
    
    def _enhance_readability(self, page_id):
        """Enhance readability using the new JSON block editor"""
        try:
            logging.info("📚 Using new JSON block editor for readability enhancement")
            
            # Try to get cached blocks to avoid re-fetching
            cached_blocks = self._get_cached_blocks(page_id)
            
            # Use the new block editor with JSON+text AI processing
            test_whole_page_json_edit(
                page_id=page_id,
                ai_model=self.reading_ai,
                dry_run=self.dry_run,
                dry_dry_run=False,
                limit_blocks=self.num_blocks,
                prompt_file="prompts.txt",
                section="Reading",
                cached_blocks=cached_blocks,
                unsync_blocks=self.unsync_blocks
            )
            
            # Since test_whole_page_json_edit handles the processing and prints results,
            # we'll return a simplified success response
            return {
                'success': True,
                'content_generated': True,
                'applied': not self.dry_run,
                'message': 'Readability enhancement completed using JSON block editor'
            }
            
        except Exception as e:
            logging.error(f"❌ Reading enhancement failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _translate_content(self, page_id, target_language):
        """Translate content using the new JSON block editor"""
        try:
            logging.info(f"🌍 Using JSON block editor for translation to {target_language}")
            
            # Try to get cached blocks to avoid re-fetching
            cached_blocks = self._get_cached_blocks(page_id)
            
            # Use the new block editor with proper translation parameters
            test_whole_page_json_edit(
                page_id=page_id,
                ai_model=self.reading_ai,  # Use reading AI for translation
                dry_run=self.dry_run,
                dry_dry_run=False,
                limit_blocks=self.num_blocks,
                prompt_file="prompts.txt",
                section="Translation",
                target_language=target_language,
                cached_blocks=cached_blocks
            )
            
            return {
                'success': True,
                'content_generated': True,
                'applied': not self.dry_run,
                'target_language': target_language,
                'message': f'Translation to {target_language} completed using JSON block editor'
            }
            
        except Exception as e:
            logging.error(f"❌ Translation to {target_language} failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'blocks_updated': 0
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
    parser = argparse.ArgumentParser(description='Run complete AI enhancement workflow on Notion page(s)')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('page_id', nargs='?', help='Single Notion page ID or URL')
    group.add_argument('--file', '-f', help='File containing page IDs (one per line)')
    parser.add_argument('--ai', default='claude', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model to use for all tasks (default: claude) - can be overridden by specific flags')
    parser.add_argument('--reading-ai', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model specifically for reading level adaptation (overrides --ai)')
    parser.add_argument('--questions-ai', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model specifically for trainer questions (overrides --ai)')
    parser.add_argument('--culture-ai', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model specifically for cultural suggestions (overrides --ai)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be done without making changes')
    parser.add_argument('--only', choices=['scrape', 'questions', 'culture', 'reading', 'translation'],
                      help='Run only a specific step instead of the full workflow')
    parser.add_argument('--force-refresh', action='store_true', 
                      help='Force refresh cached data by running scrape first')
    parser.add_argument('--target-lang', '-tl', help='Target language for translation (when using --only translation)')
    parser.add_argument('--num-blocks', type=int, help='Limit number of blocks to process (for testing)')
    parser.add_argument('--prompt-from-file', help='Custom prompt file to override prompts.txt')
    parser.add_argument('--section', default='Reading', choices=['Reading', 'Translation', 'Culture'],
                      help='Prompt section to use from prompts file (default: Reading)')
    parser.add_argument('--max-depth', type=int, default=8, help='Maximum recursion depth for block traversal')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--unsync-blocks', action='store_true', 
                      help='Convert synced blocks to regular blocks before processing')
    parser.add_argument('--notify-sms', action='store_true', 
                      help='Send SMS notifications for page completion progress (requires email setup)')
    parser.add_argument('--notify-system', action='store_true', 
                      help='Send system notifications for page completion (requires plyer: pip install plyer)')
    
    args = parser.parse_args()
    
    # Parse page IDs (single or multiple from file)
    page_ids = []
    
    if args.page_id:
        # Single page ID
        extracted_id = extract_page_id_from_text(args.page_id)
        if not extracted_id:
            logging.error(f"Could not extract page ID from: {args.page_id}")
            sys.exit(1)
        page_ids = [extracted_id]
        logging.info(f"Input: {args.page_id}")
        logging.info(f"Extracted Page ID: {extracted_id}")
        
    elif args.file:
        # Multiple page IDs from file
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    extracted_id = extract_page_id_from_text(line)
                    if extracted_id:
                        page_ids.append(extracted_id)
                    else:
                        logging.warning(f"Could not extract page ID from: {line}")
        except FileNotFoundError:
            logging.error(f"File not found: {args.file}")
            sys.exit(1)
        
        logging.info(f"Input file: {args.file}")
        logging.info(f"Extracted {len(page_ids)} page IDs")
    
    if not page_ids:
        logging.error("No valid page IDs found")
        sys.exit(1)
    
    # Determine AI models to use
    reading_ai = args.reading_ai if args.reading_ai else args.ai
    questions_ai = args.questions_ai if args.questions_ai else args.ai
    culture_ai = args.culture_ai if args.culture_ai else args.ai
    
    # Initialize orchestrator
    orchestrator = NotionOrchestrator(
        reading_ai=reading_ai,
        questions_ai=questions_ai,
        culture_ai=culture_ai,
        dry_run=args.dry_run,
        num_blocks=args.num_blocks,
        unsync_blocks=args.unsync_blocks,
        notify_sms=args.notify_sms,
        notify_system=args.notify_system
    )
    
    # Handle force refresh (only for single page processing)
    if args.force_refresh:
        if len(page_ids) > 1:
            logging.error("Force refresh is only supported for single page processing")
            sys.exit(1)
        logging.info("Force refresh requested - running scrape first...")
        scrape_result = orchestrator._scrape_page(page_ids[0])
        if not scrape_result.get('success'):
            logging.error("Failed to refresh cached data")
            sys.exit(1)
        logging.info("Cached data refreshed successfully")
    
    # Run single step if requested
    if args.only:
        step = args.only
        
        if len(page_ids) == 1:
            # Single page processing
            page_id = page_ids[0]
            if step == 'scrape':
                res = orchestrator._scrape_page(page_id)
            elif step == 'questions':
                res = orchestrator._generate_and_insert_questions(page_id)
            elif step == 'culture':
                res = orchestrator._generate_and_insert_cultural_adaptations(page_id)
            elif step == 'reading':
                res = orchestrator._enhance_readability(page_id)
            else:  # translation
                if not args.target_lang:
                    logging.error("--target-lang is required when using --only translation")
                    sys.exit(1)
                res = orchestrator._translate_content(page_id, args.target_lang)
        else:
            # Batch processing for single step
            if step == 'translation' and not args.target_lang:
                logging.error("--target-lang is required when using --only translation")
                sys.exit(1)
            
            logging.info(f"🚀 Running {step} step on {len(page_ids)} pages...")
            batch_results = orchestrator._run_batch_single_step(page_ids, step, args.target_lang if step == 'translation' else None)
            
            # Print batch results summary
            print("\n" + "="*60)
            print(f"BATCH {step.upper()} RESULTS SUMMARY")
            print("="*60)
            print(f"Total Pages: {batch_results.get('total_pages', 'N/A')}")
            print(f"Completed Successfully: {batch_results.get('completed_pages', 'N/A')}")
            print(f"Failed: {batch_results.get('failed_pages', 'N/A')}")
            print(f"Overall Success: {batch_results.get('overall_success', False)}")
            
            if batch_results.get('failed_pages', 0) > 0:
                print(f"\nFailed pages:")
                for i, page_result in enumerate(batch_results.get('page_results', []), 1):
                    if not page_result.get('success', False):
                        page_id = page_result.get('page_id', 'Unknown')
                        error = page_result.get('error', 'Unknown error')
                        print(f"  {i}. {page_id[:8]}... - {error}")
            
            sys.exit(0 if batch_results.get('overall_success') else 1)

        print("\n" + "="*60)
        print(f"STEP RESULT: {step.upper()}")
        print("="*60)
        status = "✅" if res.get('success') else "❌"
        print(f"Status: {status}")
        if 'message' in res:
            print(f"Message: {res['message']}")
        if step == 'culture':
            print(f"Adaptations added: {res.get('adaptations_added', 0)}")
        if step == 'reading':
            print(f"Successful updates: {res.get('successful_updates', 0)}")
        if step == 'translation':
            print(f"Target language: {res.get('target_language', 'Unknown')}")
            print(f"Successful updates: {res.get('successful_updates', 0)}")
        sys.exit(0 if res.get('success') else 1)

    # Check for synced blocks if unsync option is enabled (only for single page processing)
    if args.unsync_blocks:
        if len(page_ids) > 1:
            logging.error("Synced block checking (--unsync-blocks) is only supported for single page processing")
            sys.exit(1)
        
        logging.info("Checking for synced blocks...")
        from synced_block_scanner import scan_for_synced_blocks
        
        try:
            synced_info = scan_for_synced_blocks(page_ids[0])
            if synced_info:
                print(f"\n⚠️  SYNCED BLOCKS DETECTED: {len(synced_info)} synced blocks found!")
                print("Please manually unsync these blocks in the Notion UI before proceeding:")
                print()
                for block_info in synced_info:
                    print(f"  {block_info['number']}. {block_info['type']} - {block_info.get('preview', 'No preview')}")
                    print(f"     Block ID: {block_info['block_id']}")
                    print(f"     BEFORE: {block_info.get('previous_block', 'N/A')}")
                    print(f"     AFTER: {block_info.get('next_block', 'N/A')}")
                    print(f"     Page: {block_info['page_title']}")
                    print()
                
                print("Instructions:")
                print("1. Open the page in Notion")
                print("2. Find each synced block listed above")
                print("3. Click on the synced block")
                print("4. Look for the 'Unsync' option in the block menu")
                print("5. Click 'Unsync' to convert it to regular blocks")
                print()
                
                response = input("Have you manually unsynced all the blocks? (y/N): ").strip().lower()
                if response not in ['y', 'yes']:
                    print("❌ Workflow cancelled. Please unsync the blocks and run again.")
                    sys.exit(1)
                print("✅ Continuing with workflow...")
            else:
                print("✅ No synced blocks found, proceeding with workflow.")
        except Exception as e:
            logging.error(f"❌ Error checking for synced blocks: {e}")
            print(f"⚠️  Could not check for synced blocks: {e}")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                sys.exit(1)

    # Run workflow (single or batch)
    if len(page_ids) == 1:
        # Single page workflow
        results = orchestrator.run_complete_workflow(page_ids[0])
        
        # Print results summary
        print("\n" + "="*60)
        print("WORKFLOW RESULTS SUMMARY")
        print("="*60)
        print(f"Page ID: {results.get('page_id', 'N/A')}")
        ai_models = results.get('ai_models', {})
        print(f"AI Models:")
        print(f"  Reading: {ai_models.get('reading', 'N/A')}")
        print(f"  Questions: {ai_models.get('questions', 'N/A')}")
        print(f"  Culture: {ai_models.get('culture', 'N/A')}")
        print(f"Dry Run: {results.get('dry_run', 'N/A')}")
        print(f"Overall Success: {results.get('success', False)}")
        print(f"Timestamp: {results.get('timestamp', 'N/A')}")
    else:
        # Batch workflow
        results = orchestrator.run_batch_workflow(page_ids)
        
        # Print batch results summary
        print("\n" + "="*60)
        print("BATCH WORKFLOW RESULTS SUMMARY")
        print("="*60)
        print(f"Total Pages: {results.get('total_pages', 'N/A')}")
        print(f"Completed Successfully: {results.get('completed_pages', 'N/A')}")
        print(f"Failed: {results.get('failed_pages', 'N/A')}")
        ai_models = results.get('ai_models', {})
        print(f"AI Models:")
        print(f"  Reading: {ai_models.get('reading', 'N/A')}")
        print(f"  Questions: {ai_models.get('questions', 'N/A')}")
        print(f"  Culture: {ai_models.get('culture', 'N/A')}")
        print(f"Dry Run: {results.get('dry_run', 'N/A')}")
        print(f"Overall Success: {results.get('overall_success', False)}")
        print(f"Timestamp: {results.get('timestamp', 'N/A')}")
    
    if len(page_ids) == 1:
        # Single page step results
        print("\nSTEP RESULTS:")
        for step_name, step_result in results.get('steps', {}).items():
            status = "✅" if step_result.get('success') else "❌"
            print(f"{status} {step_name.title()}: {step_result.get('message', 'Completed')}")
        
        if not results.get('success', False):
            error_msg = results.get('error', 'Unknown error')
            print(f"\nWorkflow failed: {error_msg}")
            sys.exit(1)
    else:
        # Batch processing results
        if results.get('failed_pages', 0) > 0:
            print(f"\nFailed pages:")
            for i, page_result in enumerate(results.get('page_results', []), 1):
                if not page_result.get('success', False):
                    page_id = page_result.get('page_id', 'Unknown')
                    error = page_result.get('error', 'Unknown error')
                    print(f"  {i}. {page_id[:8]}... - {error}")
        
        if not results.get('overall_success', False):
            print(f"\nBatch processing completed with {results.get('failed_pages', 0)} failures")
            sys.exit(1)
    
    print("\nWorkflow completed successfully!")

if __name__ == "__main__":
    main()