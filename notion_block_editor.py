#!/usr/bin/env python3
"""
Notion Block Editor

The main Notion block editor that handles JSON+text AI processing for entire pages.
It scrapes all blocks (including children), processes each with AI for enhancement,
and writes the updated blocks back to the page with proper formatting preservation.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
from ai_handler import AIHandler
from language_codes import get_language_code

# Language detection
try:
    from langdetect import detect, DetectorFactory
    # Set seed for consistent results
    DetectorFactory.seed = 0
    LANGUAGE_DETECTION_AVAILABLE = True
except ImportError:
    LANGUAGE_DETECTION_AVAILABLE = False
    print("Warning: langdetect not installed. Install with: pip install langdetect")
    print("Language detection will be skipped.")

# Add utils directory to path for utility imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from file_finder import find_markdown_file_by_page_id

# Load environment variables
load_dotenv()


def should_skip_translation(text, target_language, source_language='english'):
    """2-step language detection: check if source OR target language to skip AI"""
    if not LANGUAGE_DETECTION_AVAILABLE or not text.strip() or not source_language:
        return False
    
    # Skip very short text (unreliable detection) - but lower threshold for common words
    text_len = len(text.strip())
    if text_len < 5:
        return False
    
    try:
        detected_lang = detect(text)
        source_code = get_language_code(source_language)
        target_code = get_language_code(target_language)
        
        # Step 1: Check if it's in source language (needs translation)
        if detected_lang == source_code:
            return False  # Needs translation
        
        # Step 2: Check if it's already in target language (skip)
        if detected_lang == target_code:
            return True  # Already translated
            
        # # Step 3: For very short text, try more aggressive matching
        # if text_len < 15:
        #     # Common patterns that are likely already translated
        #     if _is_likely_translated_short_text(text, target_code, source_code):
        #         return True
        
        # If in some other language, let AI decide
        return False
            
    except Exception:
        # If detection fails, don't skip (let AI handle it)
        return False

def _is_likely_translated_short_text(text, target_code, source_code):
    """Check if short text is likely already translated based on patterns"""
    text_lower = text.lower().strip()
    
    # Indonesian patterns
    if target_code == 'id':
        indonesian_patterns = [
            'menit', 'jam', 'hari', 'minggu', 'bulan', 'tahun',  # time units
            'orang', 'peserta', 'kelompok', 'tim',  # people
            'aktivitas', 'kegiatan', 'latihan',  # activities  
            'diskusi', 'presentasi', 'evaluasi',  # tasks
            'ya', 'tidak', 'atau', 'dan', 'dengan',  # common words
            'untuk', 'dari', 'ke', 'pada', 'di',  # prepositions
        ]
        return any(pattern in text_lower for pattern in indonesian_patterns)
    
    # Spanish patterns  
    elif target_code == 'es':
        spanish_patterns = [
            'minutos', 'horas', 'días', 'semanas', 'meses', 'años',
            'personas', 'participantes', 'grupos', 'equipos',
            'actividad', 'ejercicio', 'discusión', 'presentación',
            'sí', 'no', 'y', 'o', 'con', 'para', 'de', 'en',
        ]
        return any(pattern in text_lower for pattern in spanish_patterns)
    
    # French patterns
    elif target_code == 'fr':
        french_patterns = [
            'minutes', 'heures', 'jours', 'semaines', 'mois', 'années',
            'personnes', 'participants', 'groupes', 'équipes',
            'activité', 'exercice', 'discussion', 'présentation',
            'oui', 'non', 'et', 'ou', 'avec', 'pour', 'de', 'dans',
        ]
        return any(pattern in text_lower for pattern in french_patterns)
    
    return False

def load_prompt_from_file(path: str = "prompts.txt", section: str = "Reading") -> str:
    """
    Load a prompt from prompts.txt by section name
    
    Args:
        path (str): Path to prompts file
        section (str): Section name (Reading, Translation, Culture, etc.)
        
    Returns:
        str: The prompt text
    """
    try:
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
        # Exit immediately if prompt loading fails - don't guess
        print(f"FATAL ERROR: Failed to load prompt from {path}: {e}")
        print(f"Cannot proceed without proper prompt. Please check:")
        print(f"1. {path} exists and is readable")
        print(f"2. Section '{section}' exists in the file")
        print(f"3. Section has properly formatted triple-quoted prompt")
        sys.exit(1)

def get_all_blocks_recursively(client, page_id, max_depth=20, debug=False):
    """
    Get all blocks from a page recursively
    
    Args:
        client: Notion client
        page_id (str): Page ID
        max_depth (int): Maximum recursion depth
        debug (bool): Enable debug output
        
    Returns:
        list: All blocks with metadata
    """
    def get_children_recursive(block_id, depth=0, debug=False):
        if depth >= max_depth:
            return []
        
        all_children = []
        start_cursor = None
        
        try:
            while True:
                if debug and depth < 3:  # Only debug first few levels to avoid spam
                    print(f"    {'  ' * depth}Fetching children of {block_id} at depth {depth}")
                
                response = client.blocks.children.list(
                    block_id=block_id,
                    page_size=100,
                    start_cursor=start_cursor
                )
                
                children = response.get('results', [])
                if debug and depth < 3:
                    print(f"    {'  ' * depth}Got {len(children)} children")
                
                for child in children:
                    child_id = child.get('id', 'unknown')
                    child_type = child.get('type', 'unknown')
                    
                    # Add metadata about hierarchy
                    child['_metadata'] = {
                        'parent_id': block_id,
                        'depth': depth
                    }
                    all_children.append(child)
                    
                    # Special logging for our target Instructions block
                    is_target_block = child_id == '25072d5a-f2de-806a-990a-c23f57158d92'
                    
                    if debug and depth < 3:
                        # Get a content snippet for better debugging (with unicode safety)
                        content_snippet = ""
                        try:
                            if child_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                                             'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'toggle']:
                                rich_text = child.get(child_type, {}).get('rich_text', [])
                                content_snippet = ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])[:30]
                            elif child_type == 'image':
                                caption = child.get('image', {}).get('caption', [])
                                content_snippet = ''.join([rt.get('text', {}).get('content', '') for rt in caption])[:30]
                            elif child_type == 'table_row':
                                cells = child.get('table_row', {}).get('cells', [])
                                if cells:
                                    first_cell = ''.join([rt.get('text', {}).get('content', '') for rt in cells[0]])[:20]
                                    content_snippet = f"[{first_cell}...]"
                            elif child_type == 'embed':
                                caption = child.get('embed', {}).get('caption', [])
                                content_snippet = ''.join([rt.get('text', {}).get('content', '') for rt in caption])[:30]
                            
                            # Make content safe for Windows console
                            content_snippet = content_snippet.encode('ascii', 'replace').decode('ascii')
                        except Exception:
                            content_snippet = "[content extraction error]"
                        
                        content_display = f" '{content_snippet}'" if content_snippet else ""
                        print(f"    {'  ' * depth}  - {child_type} {child_id}{content_display} (has_children: {child.get('has_children', False)})")
                        if is_target_block:
                            print(f"    {'  ' * depth}    TARGET INSTRUCTIONS BLOCK FOUND!")
                            print(f"    {'  ' * depth}    Full data: has_children={child.get('has_children')}, type={child.get('type')}, archived={child.get('archived')}")
                    
                    # Get children recursively, but skip synced blocks
                    has_children = child.get('has_children', False)
                    block_type = child.get('type')
                    is_synced = block_type == 'synced_block'
                    
                    if debug and depth < 3 and is_target_block:
                        print(f"    {'  ' * depth}    🔍 Recursion check: has_children={has_children}, is_synced={is_synced}")
                        print(f"    {'  ' * depth}    🔍 Will recurse: {has_children and not is_synced}")
                    
                    # UPDATED: Expanded secondary check for API inconsistency
                    # Check for API inconsistency - some blocks show has_children=false but actually have children
                    container_types = ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                                     'bulleted_list_item', 'numbered_list_item', 'toggle']
                    
                    needs_secondary_check = (not has_children and 
                                           block_type in container_types and
                                           depth < 3)  # Limit depth for performance
                    
                    if (has_children and not is_synced) or needs_secondary_check:
                        try:
                            if debug and depth < 3:
                                check_type = "forced API inconsistency check" if needs_secondary_check else "standard"
                                print(f"    {'  ' * depth}    Recursing into {child_id} ({check_type})...")
                            
                            # Try to get children
                            grandchildren = get_children_recursive(child_id, depth + 1, debug)
                            
                            if grandchildren:  # Only add if we actually found children
                                all_children.extend(grandchildren)
                                if debug and depth < 3:
                                    print(f"    {'  ' * depth}    Added {len(grandchildren)} grandchildren")
                                    if needs_secondary_check:
                                        print(f"    {'  ' * depth}    SECONDARY CHECK FOUND CHILDREN! (API inconsistency confirmed)")
                            elif needs_secondary_check and debug and depth < 3:
                                print(f"    {'  ' * depth}    Secondary check confirmed no children")
                                
                        except Exception as grandchild_error:
                            print(f"  WARNING: Error getting grandchildren of {child_id} ({child_type}): {grandchild_error}")
                            if is_target_block:
                                print(f"  TARGET FAILED to get Instructions block children: {grandchild_error}")
                            # Continue processing other children even if one fails
                    elif debug and depth < 3 and is_target_block:
                        print(f"    {'  ' * depth}    NOT recursing into Instructions block: has_children={has_children}, is_synced={is_synced}")
                
                if not response.get('has_more', False):
                    break
                    
                start_cursor = response.get('next_cursor')
                
        except Exception as e:
            print(f"  CRITICAL ERROR getting children for {block_id}: {e}")
            # Return what we have so far instead of empty list
        
        return all_children
    
    print(f"Fetching all blocks from page: {page_id}")
    all_blocks = get_children_recursive(page_id, debug=debug)
    print(f"Found {len(all_blocks)} total blocks")
    
    return all_blocks

def extract_plain_text_from_block(block_data):
    """Extract plain text from block data"""
    block_type = block_data.get('type', '')
    
    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                     'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'toggle']:
        rich_text = block_data.get(block_type, {}).get('rich_text', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
    elif block_type == 'image':
        # Extract text from image caption
        caption = block_data.get('image', {}).get('caption', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in caption])
    elif block_type == 'table':
        # Tables don't have direct text content - they contain table_row children
        # The text is in the child table_row blocks, which should be processed separately
        # Return empty string so table containers are skipped from processing
        return ""
    elif block_type == 'table_row':
        # Extract text from all cells in the row
        cells = block_data.get('table_row', {}).get('cells', [])
        cell_texts = []
        for cell in cells:
            cell_text = ''.join([rt.get('text', {}).get('content', '') for rt in cell])
            cell_texts.append(cell_text)
        return ' | '.join(cell_texts)  # Join cells with pipe separator
    elif block_type == 'embed':
        # Extract text from embed caption
        caption = block_data.get('embed', {}).get('caption', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in caption])
    
    return ""

def should_process_block(block_data):
    """Determine if a block should be processed by AI"""
    block_type = block_data.get('type', '')
    
    # Skip synced blocks (we don't recurse into them anyway)
    if block_type == 'synced_block':
        return False
    
    # Only process blocks with text content
    processable_types = [
        'paragraph', 'heading_1', 'heading_2', 'heading_3',
        'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'image',
        'toggle', 'table_row', 'embed'
    ]
    
    if block_type not in processable_types:
        return False
    
    # Check if block has text content
    plain_text = extract_plain_text_from_block(block_data)
    return len(plain_text.strip()) > 0

def get_original_page_context(page_id):
    """Get original page context from cached markdown file"""
    try:
        markdown_file = find_markdown_file_by_page_id(page_id)
        if not markdown_file:
            print("    No cached markdown file found for original context")
            return ""
        
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove markdown formatting for cleaner context
        content = content.replace('#', '').replace('**', '').replace('*', '')
        content = '\n'.join([line.strip() for line in content.split('\n') if line.strip()])
        return content
    except Exception as e:
        print(f"    Warning: Could not load original page context: {e}")
        return ""

def build_enhanced_context(results_log):
    """Build enhanced context from successfully processed blocks"""
    enhanced_blocks = [r for r in results_log if r['status'] == 'enhanced' and r.get('changes_made', False)]
    
    if not enhanced_blocks:
        return ""
    
    context = "\n=== ENHANCED CONTENT SO FAR ===\n"
    for result in enhanced_blocks[-10:]:  # Last 10 enhanced blocks to avoid too much context
        context += f"• {result.get('enhanced_text', '')}\n"
    context += "=== END ENHANCED CONTENT ===\n"
    
    return context

def create_json_enhancement_prompt(block_data, plain_text, prompt_file="prompts.txt", section="Reading", target_language=None, original_page_context="", enhanced_context=""):
    """Create a prompt for AI enhancement using prompts from file"""
    # Load base prompt from prompts.txt
    base_prompt = load_prompt_from_file(prompt_file, section)
    
    # For translation section, modify prompt to include target language
    if section == "Translation" and target_language:
        base_prompt = base_prompt.replace(
            "Translate the content while carefully preserving",
            f"Translate the content to {target_language} while carefully preserving"
        )
    
    # Adapt the prompts.txt format for JSON block processing
    # The prompts.txt format uses placeholders like {block_type}, {current_plain_text}, etc.
    block_type = block_data.get('type', 'unknown')
    
    # Create formatting description (simplified for JSON approach)
    detailed_formatting = f"JSON block structure with rich_text formatting"
    
    # Build comprehensive context info
    context_parts = ["Block-by-block processing with JSON structure preservation"]
    
    if enhanced_context:
        context_parts.append(f"\nPREVIOUSLY ENHANCED BLOCKS: {enhanced_context}")
    
    if original_page_context:
        # Truncate original context to avoid overwhelming the AI
        truncated_context = original_page_context[:2000] + "..." if len(original_page_context) > 2000 else original_page_context
        context_parts.append(f"\nFULL PAGE CONTEXT (for term consistency): {truncated_context}")
    
    context_parts.append("\nIMPORTANT: Only define terms on FIRST occurrence. If you see a term was already defined in the page context or enhanced blocks above, do not define it again.")
    
    context_info = "\n".join(context_parts)
    
    # Replace placeholders in the base prompt
    adapted_prompt = base_prompt.format(
        block_type=block_type,
        current_plain_text=plain_text,
        detailed_formatting=detailed_formatting,
        context_info=context_info
    )
    
    # Add JSON-specific instructions
    json_instructions = f"""

ORIGINAL BLOCK JSON:
```json
{json.dumps(block_data, indent=2)}
```

ORIGINAL PLAIN TEXT:
"{plain_text}"

CRITICAL JSON PROCESSING REQUIREMENTS:
You must return a complete JSON object that:
1. Maintains the exact same structure as the input JSON
2. Only modifies the "content" fields within "text" objects in "rich_text" arrays
3. Preserves ALL formatting annotations (bold, italic, color, etc.)
4. Keeps all other fields identical (id, type, parent, timestamps, etc.)

If the content doesn't need improvement, return "NO CHANGES".

IMPROVED BLOCK JSON:"""
    
    return adapted_prompt + json_instructions

def parse_json_from_response(response):
    """Extract and parse JSON from AI response with multiple strategies"""
    try:
        # Strategy 1: Look for ```json blocks
        if '```json' in response:
            json_start = response.find('```json') + 7
            json_end = response.find('```', json_start)
            json_str = response[json_start:json_end].strip()
        # Strategy 2: Look for { } blocks
        elif '{' in response and '}' in response:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
        # Strategy 3: Try the whole response
        else:
            json_str = response.strip()
            
        return json.loads(json_str)
        
    except json.JSONDecodeError:
        return None

def get_ai_response_with_json_retry(ai_handler, original_prompt, block_id, plain_text, max_retries=2):
    """Get AI response with JSON retry logic - returns (response, retry_count)"""
    
    for attempt in range(max_retries):
        print(f"    AI request attempt {attempt + 1}/{max_retries}")
        
        if attempt == 0:
            # First attempt: use original prompt
            prompt = original_prompt
            temperature = 0.3
        elif attempt == 1:
            # Second attempt: ask to fix JSON format
            prompt = f"""The previous response had invalid JSON format. Please provide a valid JSON response.

ORIGINAL REQUEST:
{original_prompt}

CRITICAL: Return ONLY a valid JSON object that matches the original block structure. Do not include markdown code blocks or extra text."""
            temperature = 0.1  # Lower temperature for more consistent formatting
        else:
            # Final attempts: simplified request  
            block_type = block_id.split('-')[0] if '-' in block_id else 'paragraph'
            prompt = f"""Please enhance this text and return ONLY a valid JSON object:

Original text: "{plain_text}"

Return a JSON object with the same structure as the original block, with only the text content improved for ESL learners. No markdown, no explanations, ONLY the JSON object."""
            temperature = 0.0  # Most deterministic
        
        try:
            response = ai_handler.get_response(prompt, max_tokens=4000, temperature=temperature)
            
            # First check for "NO CHANGES" before trying to parse JSON
            if response.strip().upper() in ['NO CHANGES', 'NO CHANGE', 'NOCHANGES']:
                return response, attempt
            
            # Then test if this response can be parsed as JSON
            parsed = parse_json_from_response(response)
            if parsed is not None:
                return response, attempt
            
            print(f"    ✗ Attempt {attempt + 1} failed JSON parsing")
            
        except Exception as e:
            print(f"    ✗ Attempt {attempt + 1} failed with error: {e}")
            continue
    
    # All attempts failed, return the last response anyway
    print(f"    ⚠ All {max_retries} attempts failed, returning last response")
    return response if 'response' in locals() else "ERROR: No valid response received", max_retries - 1

def process_block_with_ai(block_data, ai_handler, results_log, dry_dry_run=False, prompt_file="prompts.txt", section="Reading", target_language=None, source_language='english', original_page_context="", enhanced_context=""):
    """Process a single block with AI"""
    block_id = block_data.get('id', 'unknown')
    block_type = block_data.get('type', 'unknown')
    
    # Extract text
    plain_text = extract_plain_text_from_block(block_data)
    
    print(f"  Processing {block_type} block {block_id}...")
    # Make text safe for Windows console
    safe_text = plain_text.encode('ascii', 'replace').decode('ascii')
    print(f"    Text: {safe_text[:50]}{'...' if len(safe_text) > 50 else ''}")
    
    # Check if translation can be skipped for Translation mode
    if section == "Translation" and target_language and should_skip_translation(plain_text, target_language, source_language):
        # Determine skip reason for better logging
        try:
            if LANGUAGE_DETECTION_AVAILABLE:
                detected = detect(plain_text) if len(plain_text.strip()) >= 5 else 'unknown'
                target_code = get_language_code(target_language)
                if detected == target_code:
                    skip_reason = f"Already in {target_language}"
                elif len(plain_text.strip()) < 15 and _is_likely_translated_short_text(plain_text, target_code, get_language_code(source_language)):
                    skip_reason = f"Pattern match: {target_language}"
                else:
                    skip_reason = f"Not {source_language}"
            else:
                skip_reason = "Language detection unavailable"
        except:
            skip_reason = f"Not {source_language}"
            
        print(f"    SKIPPED: {skip_reason}")
        results_log.append({
            'block_id': block_id,
            'status': 'skipped',
            'reason': 'already_translated',
            'original_text': plain_text,
            'source_language': source_language,
            'target_language': target_language,
            'skip_reason': skip_reason
        })
        return None
    
    # If dry-dry run, skip AI processing
    if dry_dry_run:
        print(f"    [DRY-DRY RUN] Would send to AI for enhancement")
        results_log.append({
            'block_id': block_id,
            'block_type': block_type,
            'status': 'dry_dry_run',
            'original_text': plain_text,
            'text_length': len(plain_text)
        })
        return None
    
    # Create prompt
    prompt = create_json_enhancement_prompt(block_data, plain_text, prompt_file, section, target_language, original_page_context, enhanced_context)
    
    try:
        # Get AI response with retry logic
        response, retry_count = get_ai_response_with_json_retry(
            ai_handler, prompt, block_id, plain_text, max_retries=2
        )
        
        # Check for "NO CHANGES"
        if response.strip().upper() in ['NO CHANGES', 'NO CHANGE', 'NOCHANGES']:
            print(f"    NO CHANGES needed")
            results_log.append({
                'block_id': block_id,
                'status': 'no_changes',
                'original_text': plain_text,
                'retry_count': retry_count
            })
            return None
        
        # Parse the JSON (this should work now due to retry logic)
        parsed_json = parse_json_from_response(response)
        
        # Validate that the block type hasn't been changed
        if parsed_json and parsed_json.get('type') != block_type:
            print(f"    ⚠ AI changed block type from {block_type} to {parsed_json.get('type')}, fixing...")
            parsed_json['type'] = block_type
        
        if parsed_json is None:
            # Final JSON parsing failed even after retries - return original to preserve content
            print(f"    ✗ JSON parsing failed after {retry_count + 1} attempts, preserving original")
            results_log.append({
                'block_id': block_id,
                'status': 'json_error_preserved',
                'error': 'JSON parsing failed after all retries, original preserved',
                'original_text': plain_text,
                'retry_count': retry_count,
                'final_response': response[:200] + '...' if len(response) > 200 else response
            })
            # Return original block_data to preserve content instead of losing it
            return block_data
        
        # Extract enhanced text
        enhanced_text = extract_plain_text_from_block(parsed_json)
        
        # Make enhanced text safe for Windows console
        safe_enhanced = enhanced_text.encode('ascii', 'replace').decode('ascii')
        print(f"    ENHANCED: {safe_enhanced[:50]}{'...' if len(safe_enhanced) > 50 else ''}")
        if retry_count > 0:
            print(f"    (Success after {retry_count + 1} attempts)")
        
        results_log.append({
            'block_id': block_id,
            'status': 'enhanced',
            'original_text': plain_text,
            'enhanced_text': enhanced_text,
            'changes_made': plain_text != enhanced_text,
            'retry_count': retry_count
        })
        
        return parsed_json
        
    except Exception as e:
        print(f"    ✗ Processing failed: {e}")
        results_log.append({
            'block_id': block_id,
            'status': 'error',
            'error': str(e),
            'original_text': plain_text
        })
        return None

def update_block_in_notion(client, block_id, updated_block_data, dry_run=True):
    """Update a block in Notion"""
    if dry_run:
        print(f"    [DRY RUN] Would update block {block_id}")
        return True
    
    try:
        # Extract just the content part for updating
        block_type = updated_block_data.get('type')
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3',
                         'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'toggle']:
            
            rich_text = updated_block_data.get(block_type, {}).get('rich_text', [])
            
            client.blocks.update(
                block_id=block_id,
                **{block_type: {'rich_text': rich_text}}
            )
            
            print(f"    UPDATED {block_type} block {block_id}")
            return True
            
        elif block_type == 'image':
            # Update image caption
            caption = updated_block_data.get('image', {}).get('caption', [])
            
            client.blocks.update(
                block_id=block_id,
                image={'caption': caption}
            )
            
            print(f"    UPDATED image caption {block_id}")
            return True
            
        elif block_type == 'table_row':
            # Update table row cells
            cells = updated_block_data.get('table_row', {}).get('cells', [])
            
            client.blocks.update(
                block_id=block_id,
                table_row={'cells': cells}
            )
            
            print(f"    UPDATED table_row block {block_id}")
            return True
            
        elif block_type == 'embed':
            # Update embed caption
            caption = updated_block_data.get('embed', {}).get('caption', [])
            
            client.blocks.update(
                block_id=block_id,
                embed={'caption': caption}
            )
            
            print(f"    UPDATED embed caption {block_id}")
            return True
            
        else:
            print(f"    WARNING: Unsupported block type for update: {block_type}")
            return False
            
    except Exception as e:
        print(f"    UPDATE FAILED: {e}")
        return False

def test_whole_page_json_edit(page_id, ai_model='claude', dry_run=True, dry_dry_run=False, limit_blocks=None, prompt_file="prompts.txt", section="Reading", max_depth=8, debug=False, target_language=None, source_language='english'):
    """Test editing a whole page with JSON approach"""
    
    # Initialize clients
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise ValueError("NOTION_API_KEY not found in environment variables")
    
    client = Client(auth=notion_token)
    ai_handler = None if dry_dry_run else AIHandler(ai_model)
    
    print(f"=== WHOLE PAGE JSON EDIT TEST ===")
    print(f"Page ID: {page_id}")
    print(f"AI Model: {ai_model if not dry_dry_run else 'NONE (dry-dry run)'}")
    print(f"Dry Run: {dry_run}")
    print(f"Dry-Dry Run (No AI): {dry_dry_run}")
    print(f"Limit: {limit_blocks or 'None'}")
    print(f"Prompt File: {prompt_file}")
    print(f"Section: {section}")
    print(f"Max Depth: {max_depth}")
    print()
    
    # Get page info
    try:
        page_info = client.pages.retrieve(page_id)
        page_title = page_info.get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Untitled')
        print(f"Page: {page_title}")
    except Exception as e:
        print(f"Error getting page info: {e}")
        return
    
    # Get all blocks
    print(f"\n1. Fetching all blocks...")
    all_blocks = get_all_blocks_recursively(client, page_id, max_depth=max_depth, debug=debug)
    
    # Filter processable blocks and count skipped types
    processable_blocks = [block for block in all_blocks if should_process_block(block)]
    synced_blocks = [block for block in all_blocks if block.get('type') == 'synced_block']
    
    if limit_blocks:
        processable_blocks = processable_blocks[:limit_blocks]
    
    print(f"   Total blocks: {len(all_blocks)}")
    print(f"   Synced blocks (skipped): {len(synced_blocks)}")
    print(f"   Processable blocks: {len(processable_blocks)}")
    
    # Get original page context
    print(f"\n2a. Loading original page context...")
    original_page_context = get_original_page_context(page_id)
    if original_page_context:
        print(f"    Original page context loaded: {len(original_page_context)} characters")
    else:
        print("    No original page context available")
    
    # Process blocks
    print(f"\n2. Processing blocks with AI...")
    results_log = []
    updates_made = 0
    
    for i, block in enumerate(processable_blocks, 1):
        block_id = block.get('id')
        print(f"\n   Block {i}/{len(processable_blocks)}")
        
        # Build enhanced context from blocks processed so far
        enhanced_context = build_enhanced_context(results_log)
        
        # Process with AI (or skip if dry-dry run)
        updated_block = process_block_with_ai(
            block, ai_handler, results_log, dry_dry_run, prompt_file, section, 
            target_language, source_language, original_page_context, enhanced_context
        )
        
        # Update in Notion if changes were made
        if updated_block:
            success = update_block_in_notion(client, block_id, updated_block, dry_run)
            if success:
                updates_made += 1
    
    # Save results
    print(f"\n3. Saving results...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path('test_results')
    results_dir.mkdir(exist_ok=True)
    
    results_data = {
        'test_info': {
            'page_id': page_id,
            'page_title': page_title,
            'ai_model': ai_model,
            'dry_run': dry_run,
            'dry_dry_run': dry_dry_run,
            'timestamp': timestamp,
            'limit': limit
        },
        'summary': {
            'total_blocks': len(all_blocks),
            'synced_blocks_skipped': len(synced_blocks),
            'processable_blocks': len(processable_blocks),
            'updates_made': updates_made,
            'no_changes': len([r for r in results_log if r['status'] == 'no_changes']),
            'errors': len([r for r in results_log if r['status'] in ['error', 'json_error']])
        },
        'detailed_results': results_log
    }
    
    results_file = results_dir / f"whole_page_edit_{page_id[:8]}_{ai_model}_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)
    
    print(f"   Results saved to: {results_file}")
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Total blocks found: {len(all_blocks)}")
    print(f"Synced blocks (skipped): {len(synced_blocks)}")
    print(f"Processable blocks: {len(processable_blocks)}")
    print(f"Updates made: {updates_made}")
    print(f"No changes needed: {len([r for r in results_log if r['status'] == 'no_changes'])}")
    print(f"Errors: {len([r for r in results_log if r['status'] in ['error', 'json_error']])}")
    
    if dry_run:
        print(f"\nWARNING: This was a DRY RUN - no actual changes were made to Notion")
    else:
        print(f"\nSUCCESS: Changes have been written to Notion")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Edit a whole Notion page using JSON+AI approach with formatting preservation',
        epilog='Examples:\n  Reading: python notion_block_editor.py <page_id> --mode Reading --ai claude\n  Translation: python notion_block_editor.py <page_id> --mode Translation --target-lang Indonesian --ai gemini\n  Translation (from Spanish): python notion_block_editor.py <page_id> --mode Translation --target-lang English --source-lang Spanish --ai claude\n  Culture: python notion_block_editor.py <page_id> --mode Culture --ai claude',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('page_id', help='Notion page ID to edit')
    parser.add_argument('--ai', default='claude', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model to use (default: claude)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Perform dry run without making actual changes')
    parser.add_argument('--live', action='store_true',
                      help='Make actual changes to Notion')
    parser.add_argument('--dry-dry-run', action='store_true',
                      help='Skip AI processing entirely, just show what would be processed')
    parser.add_argument('--limit', type=int, help='Limit number of blocks to process')
    parser.add_argument('--prompt-from-file', help='Custom prompt file to override prompts.txt')
    parser.add_argument('--mode', default='Reading', choices=['Reading', 'Translation', 'Culture'],
                      help='Processing mode: Reading (enhance readability), Translation (translate content), Culture (cultural analysis) (default: Reading)')
    parser.add_argument('--target-lang', help='Target language for translation (required when using --mode Translation)')
    parser.add_argument('--source-lang', default='english', help='Source language to translate from (default: english)')
    parser.add_argument('--max-depth', type=int, default=8, help='Maximum recursion depth for block traversal')
    parser.add_argument('--skip-synced', action='store_true', help='Skip synced blocks (default behavior)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.mode == 'Translation' and not args.target_lang:
        parser.error("--target-lang is required when using --mode Translation")
    
    # Determine run mode
    dry_dry_run = args.dry_dry_run
    dry_run = not args.live
    
    try:
        prompt_file = args.prompt_from_file or "prompts.txt"
        test_whole_page_json_edit(
            page_id=args.page_id, 
            ai_model=args.ai, 
            dry_run=dry_run, 
            dry_dry_run=dry_dry_run, 
            limit_blocks=args.limit,
            prompt_file=prompt_file,
            section=args.mode,
            max_depth=args.max_depth,
            debug=args.debug,
            target_language=args.target_lang,
            source_language=args.source_lang
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()