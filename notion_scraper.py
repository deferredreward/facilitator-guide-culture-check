import os
import json
import sys
import argparse
import re
from notion_client import Client
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def clean_title_for_filename(title):
    """Clean title to make it safe for use as a filename"""
    if not title or not title.strip():
        return "notion_page"
    
    # Remove or replace invalid filename characters
    # Replace with underscores: spaces, slashes, backslashes, colons, etc.
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', '_', title.strip())
    
    # Replace multiple underscores with single underscore
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # Remove leading/trailing underscores
    cleaned = cleaned.strip('_')
    
    # Limit length to avoid overly long filenames (keep reasonable length)
    if len(cleaned) > 50:
        cleaned = cleaned[:50].rstrip('_')
    
    # If cleaning results in empty string, use default
    if not cleaned:
        return "notion_page"
    
    return cleaned

def get_page_id():
    """Get page ID from command line arguments or prompt user"""
    parser = argparse.ArgumentParser(description='Scrape a Notion page to markdown')
    parser.add_argument('page_id', nargs='?', help='Notion page ID')
    parser.add_argument('--page', help='Notion page ID (alternative to positional argument)')
    
    args = parser.parse_args()
    
    # Check for page ID in arguments
    page_id = args.page_id or args.page
    
    # If no page ID provided, prompt user
    if not page_id:
        print("Enter a Notion page ID to scrape:")
        page_id = input().strip()
        
        if not page_id:
            logging.error("❌ No page ID provided")
            sys.exit(1)
    
    return page_id

def test_notion_api(page_id):
    """Test Notion API to scrape a page into markdown"""
    
    notion_token = os.getenv('NOTION_API_KEY')
    if not notion_token:
        logging.error("❌ NOTION_API_KEY not found in environment variables")
        return False
    
    try:
        notion = Client(auth=notion_token)
        logging.info("✅ Notion client initialized successfully")
    except Exception as e:
        logging.error(f"❌ Failed to initialize Notion client: {e}")
        return False
    
    try:
        logging.info(f"🔍 Attempting to retrieve page: {page_id}")
        page = notion.pages.retrieve(page_id)
        logging.info("✅ Page retrieved successfully!")
        
        title_property = page.get('properties', {}).get('Name', {}) # Changed 'title' to 'Name'
        if not title_property:
             title_property = page.get('properties', {}).get('title', {})
        
        title_text = "Untitled"
        if title_property and title_property.get('title'):
            title_text = title_property['title'][0].get('plain_text', 'Untitled')

        logging.info(f"📄 Page title: {title_text}")
        
        logging.info("🔍 Retrieving all page content (including nested blocks)...")
        all_blocks = get_all_blocks_recursively(notion, page_id)
        logging.info(f"✅ Retrieved {len(all_blocks)} total blocks")
        
        markdown_content, unknown_blocks = convert_to_markdown_enhanced(notion, page, all_blocks)
        
        # Create saved_pages directory if it doesn't exist
        saved_pages_dir = "saved_pages"
        os.makedirs(saved_pages_dir, exist_ok=True)
        
        output_file = os.path.join(saved_pages_dir, f"{clean_title_for_filename(title_text)}.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logging.info(f"✅ Enhanced markdown saved to: {output_file}")
        logging.info(f"📊 Content length: {len(markdown_content)} characters")

        if unknown_blocks:
            logging.warning(f"⚠️ Encountered unknown block types: {', '.join(unknown_blocks)}")

        debug_file = os.path.join(saved_pages_dir, f"{clean_title_for_filename(title_text)}_{page_id}_debug.json")
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump({'page': page, 'blocks': all_blocks}, f, indent=2, default=str)
        logging.info(f"🔍 Debug JSON with structural info saved to: {debug_file}")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error during page processing: {e}", exc_info=True)
        return False

def get_all_blocks_recursively(notion, block_id):
    """Recursively get all blocks including nested children, but not from child pages."""
    all_blocks = []
    
    def get_blocks(b_id):
        try:
            blocks_response = notion.blocks.children.list(b_id)
            for block in blocks_response['results']:
                all_blocks.append(block)
                # If block has children AND is not a child_page, recurse
                if block.get('has_children') and block.get('type') != 'child_page':
                    get_blocks(block['id'])
        except Exception as e:
            logging.warning(f"⚠️ Could not retrieve children for block {b_id}: {e}")
    
    get_blocks(block_id)
    return all_blocks

def convert_to_markdown_enhanced(notion, page, blocks):
    """Enhanced conversion to markdown with more block types and no user interaction."""
    markdown = []
    unknown_block_types = set()

    title_property = page.get('properties', {}).get('Name', {}) # Changed 'title' to 'Name'
    if not title_property:
        title_property = page.get('properties', {}).get('title', {})
    
    title_text = "Untitled"
    if title_property and title_property.get('title'):
        title_text = title_property['title'][0].get('plain_text', 'Untitled')

    markdown.append(f"# {title_text}\n")
    
    for i, block in enumerate(blocks):
        block_type = block.get('type')
        
        try:
            if not block_type:
                raise ValueError(f"Block at index {i} is missing 'type'")

            if block_type == 'paragraph':
                text = extract_text(block.get('paragraph', {}).get('rich_text', []))
                if text: markdown.append(f"{text}\n")
            
            elif block_type.startswith('heading_'):
                text = extract_text(block.get(block_type, {}).get('rich_text', []))
                level = block_type.split('_')[-1]
                if text: markdown.append(f"{'#' * int(level)} {text}\n")
            
            elif block_type == 'bulleted_list_item':
                text = extract_text(block.get(block_type, {}).get('rich_text', []))
                if text: markdown.append(f"- {text}\n")
            
            elif block_type == 'numbered_list_item':
                text = extract_text(block.get(block_type, {}).get('rich_text', []))
                if text: markdown.append(f"1. {text}\n")
            
            elif block_type == 'code':
                text = extract_text(block.get('code', {}).get('rich_text', []))
                language = block.get('code', {}).get('language', '')
                if text: markdown.append(f"```{language}\n{text}\n```\n")
            
            elif block_type == 'quote':
                text = extract_text(block.get('quote', {}).get('rich_text', []))
                if text: markdown.append(f"> {text}\n")

            elif block_type == 'to_do':
                text = extract_text(block.get('to_do', {}).get('rich_text', []))
                checked = block.get('to_do', {}).get('checked', False)
                if text: markdown.append(f"- [{'x' if checked else ' '}] {text}\n")
            
            elif block_type == 'synced_block':
                markdown.append("<!-- Start Synced Block -->\n")
                synced_from_id = block.get('synced_block', {}).get('synced_from', {}).get('block_id')
                if synced_from_id:
                    synced_blocks = get_all_blocks_recursively(notion, synced_from_id)
                    synced_md, new_unknowns = convert_to_markdown_enhanced(notion, {}, synced_blocks)
                    # We remove the title from the recursive call
                    markdown.append(synced_md.split('\n', 1)[-1]) 
                    unknown_block_types.update(new_unknowns)
                markdown.append("<!-- End Synced Block -->\n")

            elif block_type == 'child_page':
                title = block.get('child_page', {}).get('title', 'Link to Page')
                markdown.append(f"📄 [{title}](notion:/{block['id']})\n")
            
            elif block_type == 'image':
                img_block = block.get('image', {})
                url = img_block.get('file', {}).get('url') or img_block.get('external', {}).get('url')
                caption = extract_text(img_block.get('caption', []))
                if url: markdown.append(f"![{caption or 'image'}]({url})\n")

            elif block_type == 'video':
                video_block = block.get('video', {})
                url = video_block.get('file', {}).get('url') or video_block.get('external', {}).get('url')
                caption = extract_text(video_block.get('caption', []))
                if url: markdown.append(f"🎥 Video: [{caption or url}]({url})\n")

            elif block_type == 'file':
                file_block = block.get('file', {})
                url = file_block.get('file', {}).get('url') or file_block.get('external', {}).get('url')
                caption = extract_text(file_block.get('caption', []))
                if url: markdown.append(f"📎 File: [{caption or url}]({url})\n")
            
            elif block_type == 'embed':
                url = block.get('embed', {}).get('url')
                if url: markdown.append(f"🔗 Embed: [{url}]({url})\n")

            elif block_type == 'table':
                 # table block is a container, its children are table_rows
                pass
            
            elif block_type == 'table_row':
                cells = block.get('table_row', {}).get('cells', [])
                row_text = "| " + " | ".join([extract_text(cell) for cell in cells]) + " |"
                markdown.append(f"{row_text}\n")

            else:
                unknown_block_types.add(block_type)
                logging.warning(f"Skipping unknown block type: {block_type}")

        except Exception as e:
            logging.error(f"Error processing block {i} ({block_type}): {e}", exc_info=True)
            
    return '\n'.join(markdown), unknown_block_types

def extract_text(rich_text):
    """Extract plain text from rich text array with formatting"""
    if not rich_text: return ""
    
    parts = []
    for text_part in rich_text:
        plain_text = text_part.get('plain_text', '')
        annotations = text_part.get('annotations', {})
        if annotations.get('bold'): plain_text = f"**{plain_text}**"
        if annotations.get('italic'): plain_text = f"*{plain_text}*"
        if annotations.get('strikethrough'): plain_text = f"~~{plain_text}~~"
        if annotations.get('code'): plain_text = f"`{plain_text}`"
        
        href = text_part.get('href')
        if href: plain_text = f"[{plain_text}]({href})"
        
        parts.append(plain_text)
    
    return ''.join(parts)

if __name__ == "__main__":
    logging.info("🚀 Starting advanced Notion page scraping...")
    page_id = get_page_id()
    success = test_notion_api(page_id)
    
    if success:
        logging.info("\n🎉 Scraping process completed successfully!")
    else:
        logging.info("\n💥 Scraping process failed. Check logs for details.") 