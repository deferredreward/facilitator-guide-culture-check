#!/usr/bin/env python3
"""
File Finder Utility

This module provides functions to find scraped Notion files by page_id,
supporting both the old and new filename formats for backward compatibility.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

def find_files_by_page_id(page_id: str, saved_pages_dir: str = "saved_pages") -> Tuple[Optional[Path], Optional[Path]]:
    """
    Find markdown and debug files for a given page_id
    
    Args:
        page_id (str): The Notion page ID
        saved_pages_dir (str): Directory containing saved pages
        
    Returns:
        Tuple[Optional[Path], Optional[Path]]: (markdown_file, debug_file) or (None, None) if not found
    """
    saved_pages_path = Path(saved_pages_dir)
    
    if not saved_pages_path.exists():
        logging.error(f"❌ {saved_pages_dir} directory not found")
        return None, None
    
    # Try to find debug file first (it contains page_id in filename)
    debug_file = find_debug_file_by_page_id(page_id, saved_pages_path)
    markdown_file = None
    
    if debug_file:
        # Extract the title-based filename from the debug file
        debug_name = debug_file.stem  # Remove .json extension
        # Remove the page_id suffix to get the title part
        title_part = debug_name.replace(f"_{page_id}_debug", "")
        markdown_file = saved_pages_path / f"{title_part}.md"
        
        if not markdown_file.exists():
            logging.warning(f"⚠️ Found debug file but no corresponding markdown file: {markdown_file}")
            markdown_file = None
    
    # If we couldn't find via debug file, try the old format as fallback
    if not markdown_file:
        old_format_md = saved_pages_path / f"notion_page_{page_id}.md"
        old_format_debug = saved_pages_path / f"notion_page_{page_id}_debug.json"
        
        if old_format_md.exists():
            markdown_file = old_format_md
            logging.info(f"✅ Found markdown file using old format: {markdown_file}")
        
        if old_format_debug.exists() and not debug_file:
            debug_file = old_format_debug
            logging.info(f"✅ Found debug file using old format: {debug_file}")
    
    return markdown_file, debug_file

def find_debug_file_by_page_id(page_id: str, saved_pages_path: Path) -> Optional[Path]:
    """
    Find debug file by scanning for files containing the page_id
    
    Args:
        page_id (str): The Notion page ID
        saved_pages_path (Path): Path to saved_pages directory
        
    Returns:
        Optional[Path]: Path to debug file or None if not found
    """
    try:
        # Look for files ending with _{page_id}_debug.json
        for file_path in saved_pages_path.glob("*_debug.json"):
            if f"_{page_id}_debug.json" in file_path.name:
                logging.info(f"✅ Found debug file: {file_path}")
                return file_path
        
        logging.warning(f"⚠️ No debug file found for page_id: {page_id}")
        return None
        
    except Exception as e:
        logging.error(f"❌ Error searching for debug file: {e}")
        return None

def find_markdown_file_by_page_id(page_id: str, saved_pages_dir: str = "saved_pages") -> Optional[Path]:
    """
    Find markdown file for a given page_id
    
    Args:
        page_id (str): The Notion page ID
        saved_pages_dir (str): Directory containing saved pages
        
    Returns:
        Optional[Path]: Path to markdown file or None if not found
    """
    markdown_file, _ = find_files_by_page_id(page_id, saved_pages_dir)
    return markdown_file

def find_debug_file_by_page_id_only(page_id: str, saved_pages_dir: str = "saved_pages") -> Optional[Path]:
    """
    Find debug file for a given page_id
    
    Args:
        page_id (str): The Notion page ID
        saved_pages_dir (str): Directory containing saved pages
        
    Returns:
        Optional[Path]: Path to debug file or None if not found
    """
    _, debug_file = find_files_by_page_id(page_id, saved_pages_dir)
    return debug_file

if __name__ == "__main__":
    # Test the functions
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python file_finder.py <page_id>")
        sys.exit(1)
    
    page_id = sys.argv[1]
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(f"🔍 Searching for files with page_id: {page_id}")
    
    markdown_file, debug_file = find_files_by_page_id(page_id)
    
    if markdown_file:
        print(f"📄 Markdown file: {markdown_file}")
    else:
        print("❌ No markdown file found")
    
    if debug_file:
        print(f"🔍 Debug file: {debug_file}")
    else:
        print("❌ No debug file found") 