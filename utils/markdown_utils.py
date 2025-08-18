#!/usr/bin/env python3
"""
Markdown Utilities - Shared module for markdown processing

This module provides utilities for cleaning and processing markdown content
that can be shared across different scripts.
"""

import re
import logging

def clean_markdown_content(content):
    """Clean markdown content by removing long URLs and unnecessary content to reduce tokens"""
    
    # Remove long URLs (longer than the example provided)
    # This will catch the long AWS URLs and other long links
    max_url_length = len("notion:/dfbf4465-01eb-4338-813f-880c4cb66889")
    
    # Pattern to match markdown links and images with long URLs
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    
    def clean_link(match):
        text = match.group(1)
        url = match.group(2)
        
        # If URL is longer than our threshold, replace with a simple reference
        if len(url) > max_url_length:
            if match.group(0).startswith('!['):  # Image
                return f"![{text}](link_to_resource)"
            else:  # Regular link
                return f"[{text}](link_to_resource)"
        return match.group(0)
    
    # Clean regular links
    content = re.sub(link_pattern, clean_link, content)
    
    # Clean image links
    content = re.sub(image_pattern, clean_link, content)
    
    # Remove long standalone URLs
    url_pattern = r'https?://[^\s\)]+'
    def clean_standalone_url(match):
        url = match.group(0)
        if len(url) > max_url_length:
            return "[link_to_resource]"
        return url
    
    content = re.sub(url_pattern, clean_standalone_url, content)
    
    # Remove embed links
    content = re.sub(r'🔗 Embed: \[[^\]]*\]\([^)]+\)', '🔗 Embed: [link_to_resource]', content)
    
    # Remove file links
    content = re.sub(r'📎 File: \[[^\]]*\]\([^)]+\)', '📎 File: [link_to_resource]', content)
    
    # Remove video links
    content = re.sub(r'🎥 Video: \[[^\]]*\]\([^)]+\)', '🎥 Video: [link_to_resource]', content)
    
    logging.info(f"✅ Cleaned markdown content (removed long URLs and unnecessary links)")
    return content 