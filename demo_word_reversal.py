#!/usr/bin/env python3
"""
Demo script for word reversal functionality

This script demonstrates how the word reversal works and provides
examples of what the functionality does.
"""

import logging
from notion_writer import NotionWriter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def demo_word_reversal():
    """Demonstrate the word reversal functionality"""
    print("🎯 Word Reversal Demo")
    print("=" * 50)
    
    # Initialize writer (this will fail if no API key, but we can still demo the logic)
    try:
        writer = NotionWriter()
        print("✅ Notion client initialized successfully")
    except Exception as e:
        print(f"⚠️ Note: Notion client initialization failed: {e}")
        print("📝 Continuing with word reversal logic demo...")
        
        # Create a mock writer just for the reversal logic
        class MockWriter:
            def reverse_words_in_text(self, text):
                import re
                words = re.findall(r'\S+|\s+', text)
                reversed_words = []
                for word in words:
                    if word.strip():
                        word_match = re.match(r'^(\W*)(.*?)(\W*)$', word)
                        if word_match:
                            prefix, core_word, suffix = word_match.groups()
                            if core_word:
                                reversed_word = prefix + core_word[::-1] + suffix
                            else:
                                reversed_word = word
                        else:
                            reversed_word = word[::-1]
                        reversed_words.append(reversed_word)
                    else:
                        reversed_words.append(word)
                return ''.join(reversed_words)
        
        writer = MockWriter()
    
    # Test cases that would be found in a Notion page
    test_cases = [
        "❓ What is the purpose of this test?",
        "❓ How does this work with punctuation!",
        "❓ Testing with numbers: 123 and symbols @#$",
        "❓ Multiple words will be reversed individually",
        "❓ Single",
        "❓ This-is-hyphenated and this_is_underscored",
        "❓ Can we handle emojis? 😊 Yes we can!",
        "❓ What about URLs? https://example.com works",
        "❓ Email addresses: test@example.com should work too"
    ]
    
    print("\n🔄 Word Reversal Examples:")
    print("-" * 50)
    
    for i, original in enumerate(test_cases, 1):
        reversed_text = writer.reverse_words_in_text(original)
        print(f"{i}. Original: {original}")
        print(f"   Reversed: {reversed_text}")
        print()
    
    print("📋 Key Features:")
    print("- Finds blocks starting with ❓ emoji")
    print("- Reverses each word individually (keeps word order)")
    print("- Preserves punctuation and whitespace")
    print("- Handles hyphenated words and numbers")
    print("- Non-destructive (can be tested with --dry-run)")
    print("- Works with all Notion text block types")
    
    return True

def show_usage_instructions():
    """Show how to use the functionality"""
    print("\n📖 Usage Instructions:")
    print("=" * 50)
    
    print("1. First, make sure your Notion page is shared with your integration:")
    print("   - Go to your Notion page")
    print("   - Click 'Share' -> 'Invite'")
    print("   - Add your integration")
    
    print("\n2. Scrape the page first (if not already done):")
    print("   python notion_scraper.py 22b72d5af2de80c9b4e1edf7a45abf8f")
    
    print("\n3. Test the word reversal (dry run to see what would change):")
    print("   python test_notion_word_reversal.py 22b72d5af2de80c9b4e1edf7a45abf8f --dry-run")
    
    print("\n4. Actually perform the word reversal:")
    print("   python test_notion_word_reversal.py 22b72d5af2de80c9b4e1edf7a45abf8f")
    
    print("\n5. Or test with a different emoji:")
    print("   python test_notion_word_reversal.py 22b72d5af2de80c9b4e1edf7a45abf8f --emoji='🤔'")
    
    print("\n🔧 What the script does:")
    print("- Searches for all blocks starting with ❓ (or specified emoji)")
    print("- Shows you what would be changed (original vs reversed)")
    print("- Asks for confirmation before making changes")
    print("- Updates each block with words reversed")
    print("- Provides detailed results of what was changed")
    
    print("\n⚙️ Technical Details:")
    print("- Uses Notion API to read and write blocks")
    print("- Handles all text block types (paragraph, heading, list, etc.)")
    print("- Preserves formatting and structure")
    print("- Reverses words character by character")
    print("- Keeps punctuation with words")

def create_test_page_instructions():
    """Show how to create a test page for demonstration"""
    print("\n🧪 Creating a Test Page:")
    print("=" * 50)
    
    print("To test this functionality, create a Notion page with content like:")
    print()
    print("❓ What is the purpose of this test?")
    print("This is a regular paragraph that won't be changed.")
    print("❓ How does this work with punctuation!")
    print("❓ Testing with numbers: 123 and symbols @#$")
    print("Another regular paragraph.")
    print("❓ Multiple words will be reversed individually")
    print()
    print("Then run the script on that page to see the reversal in action!")

if __name__ == "__main__":
    print("🚀 Starting Word Reversal Demo...")
    
    # Run the demo
    demo_word_reversal()
    
    # Show usage instructions
    show_usage_instructions()
    
    # Show test page creation instructions
    create_test_page_instructions()
    
    print("\n🎉 Demo completed!") 