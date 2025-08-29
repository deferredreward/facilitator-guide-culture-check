#!/usr/bin/env python3
"""
Experimental JSON+Text AI Processing Test

This script tests sending both raw JSON and plain text to the AI to see if it can
better understand and reconstruct the formatting while making content improvements.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client
from ai_handler import AIHandler

# Load environment variables
load_dotenv()

def fetch_block(block_id):
    """Fetch a block from Notion API"""
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise ValueError("NOTION_API_KEY not found in environment variables")
    
    client = Client(auth=notion_token)
    response = client.blocks.retrieve(block_id)
    return response

def extract_plain_text_from_block(block_data):
    """Extract plain text from block data"""
    block_type = block_data.get('type', '')
    
    if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                     'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']:
        rich_text = block_data.get(block_type, {}).get('rich_text', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in rich_text])
    elif block_type == 'image':
        # Extract text from image caption
        caption = block_data.get('image', {}).get('caption', [])
        return ''.join([rt.get('text', {}).get('content', '') for rt in caption])
    
    return ""

def create_json_ai_prompt(block_data, plain_text):
    """Create a prompt that includes both JSON structure and plain text"""
    return f"""You are an expert in making technical and educational content more accessible to non-native English speakers at an 8th-grade level, while preserving complex formatting structures.

You will receive a Notion block in JSON format along with its plain text. Your task is to:
1. Understand the complete formatting structure from the JSON
2. Improve the plain text content for accessibility 
3. Return a JSON response that preserves the original structure but with enhanced content

ORIGINAL BLOCK JSON:
```json
{json.dumps(block_data, indent=2)}
```

ORIGINAL PLAIN TEXT:
"{plain_text}"

ENHANCEMENT GUIDELINES:
- Simplify complex sentence structures
- Use shorter, clearer sentences  
- Replace difficult words with simpler alternatives
- Use active voice instead of passive voice
- DO NOT change technical terms, proper nouns, or key terminology
- DO NOT change time durations like "60 minutes"
- Preserve the person/tense of the original

CRITICAL: You must return a complete JSON object that:
1. Maintains the exact same structure as the input JSON
2. Only modifies the "content" fields within "text" objects in "rich_text" arrays
3. Preserves ALL formatting annotations (bold, italic, color, etc.)
4. Keeps all other fields identical (id, type, parent, timestamps, etc.)

If the content doesn't need improvement, return the original JSON unchanged.

IMPROVED BLOCK JSON:"""

def test_json_ai_processing(block_id, ai_model='claude'):
    """Test the JSON+text AI processing approach"""
    print(f"Testing JSON AI processing with block: {block_id}")
    print(f"AI Model: {ai_model}")
    
    # Fetch the block
    print("\n1. Fetching block from Notion...")
    block_data = fetch_block(block_id)
    print(f"   Block type: {block_data.get('type', 'unknown')}")
    
    # Extract plain text
    plain_text = extract_plain_text_from_block(block_data)
    # Remove emojis for display
    display_text = ''.join(char for char in plain_text if ord(char) < 128)
    print(f"   Original text: {display_text}")
    
    # Create AI prompt
    print("\n2. Creating AI prompt with JSON+text...")
    prompt = create_json_ai_prompt(block_data, plain_text)
    
    # Get AI response
    print("\n3. Sending to AI...")
    ai_handler = AIHandler(ai_model)
    response = ai_handler.get_response(prompt, max_tokens=4000, temperature=0.3)
    
    print("\n4. AI Response:")
    print("=" * 60)
    print(response)
    print("=" * 60)
    
    # Try to parse the AI response as JSON
    print("\n5. Attempting to parse AI response as JSON...")
    try:
        # Extract JSON from response (in case AI wraps it in explanation)
        if '```json' in response:
            json_start = response.find('```json') + 7
            json_end = response.find('```', json_start)
            json_str = response[json_start:json_end].strip()
        elif '{' in response and '}' in response:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            json_str = response[json_start:json_end]
        else:
            json_str = response
            
        parsed_json = json.loads(json_str)
        print("   Successfully parsed JSON response")
        
        # Extract new plain text for comparison
        new_plain_text = extract_plain_text_from_block(parsed_json)
        new_display_text = ''.join(char for char in new_plain_text if ord(char) < 128)
        print(f"   Enhanced text: {new_display_text}")
        
        # Save results with unique naming
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = Path('test_results')
        results_dir.mkdir(exist_ok=True)
        
        results = {
            'test_info': {
                'block_id': block_id,
                'ai_model': ai_model,
                'timestamp': timestamp,
                'test_type': 'json_ai_processing'
            },
            'input': {
                'original_block': block_data,
                'original_text': plain_text
            },
            'ai_interaction': {
                'prompt_sent': prompt,
                'raw_response': response
            },
            'output': {
                'parsed_json': parsed_json,
                'enhanced_text': new_plain_text,
                'parsing_success': True
            },
            'comparison': {
                'text_changed': plain_text != new_plain_text,
                'structure_preserved': block_data.get('type') == parsed_json.get('type')
            }
        }
        
        results_file = results_dir / f"json_ai_{block_id[:8]}_{ai_model}_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"   Results saved to: {results_file}")
        
        return {
            'success': True,
            'original_text': plain_text,
            'enhanced_text': new_plain_text,
            'enhanced_block': parsed_json
        }
        
    except json.JSONDecodeError as e:
        print(f"   Failed to parse AI response as JSON: {e}")
        
        # Save failure results for analysis
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = Path('test_results')
        results_dir.mkdir(exist_ok=True)
        
        failure_results = {
            'test_info': {
                'block_id': block_id,
                'ai_model': ai_model,
                'timestamp': timestamp,
                'test_type': 'json_ai_processing',
                'status': 'FAILED'
            },
            'input': {
                'original_block': block_data,
                'original_text': plain_text
            },
            'ai_interaction': {
                'prompt_sent': prompt,
                'raw_response': response
            },
            'error': {
                'type': 'JSON_PARSE_ERROR',
                'message': str(e),
                'parsing_success': False
            }
        }
        
        failure_file = results_dir / f"json_ai_FAILED_{block_id[:8]}_{ai_model}_{timestamp}.json"
        with open(failure_file, 'w', encoding='utf-8') as f:
            json.dump(failure_results, f, indent=2, ensure_ascii=False)
        
        print(f"   Failure data saved to: {failure_file}")
        
        return {
            'success': False,
            'error': f"JSON parsing failed: {e}",
            'raw_response': response
        }

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Test JSON+text AI processing approach')
    parser.add_argument('block_id', help='Notion block ID to test')
    parser.add_argument('--ai', default='claude', choices=['claude', 'gemini', 'openai', 'xai'],
                      help='AI model to use (default: claude)')
    
    args = parser.parse_args()
    
    try:
        result = test_json_ai_processing(args.block_id, args.ai)
        
        print(f"\n{'='*60}")
        print("FINAL RESULTS")
        print(f"{'='*60}")
        
        if result['success']:
            print("Test successful!")
            orig_display = ''.join(char for char in result['original_text'] if ord(char) < 128)
            enh_display = ''.join(char for char in result['enhanced_text'] if ord(char) < 128)
            print(f"Original: {orig_display}")
            print(f"Enhanced: {enh_display}")
        else:
            print("Test failed!")
            print(f"Error: {result['error']}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()