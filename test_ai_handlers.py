#!/usr/bin/env python3
"""
Test script for AI handlers

This script tests the AI handler functionality for all supported providers.
"""

import logging
from ai_handler import create_ai_handler

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ai_handler(provider_name):
    """Test a specific AI handler"""
    print(f"\n🧪 Testing {provider_name.upper()} handler...")
    
    try:
        # Create handler
        handler = create_ai_handler(provider_name)
        
        # Simple test prompt
        test_prompt = "Please respond with just 'Hello from [provider_name]' and nothing else."
        
        # Get response
        response = handler.get_response(test_prompt, max_tokens=50, temperature=0.1)
        
        print(f"✅ {provider_name.upper()} test successful!")
        print(f"📝 Response: {response.strip()}")
        return True
        
    except Exception as e:
        print(f"❌ {provider_name.upper()} test failed: {e}")
        return False

def main():
    """Test all AI handlers"""
    print("🚀 Testing AI Handlers...")
    
    providers = ['gemini', 'claude', 'openai']
    results = {}
    
    for provider in providers:
        results[provider] = test_ai_handler(provider)
    
    print(f"\n📊 Test Results:")
    for provider, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {provider.upper()}: {status}")
    
    # Summary
    passed = sum(results.values())
    total = len(results)
    print(f"\n🎯 Summary: {passed}/{total} providers working")
    
    if passed == total:
        print("🎉 All AI handlers are working correctly!")
    else:
        print("⚠️ Some AI handlers need configuration. Check your .env file and API keys.")

if __name__ == "__main__":
    main() 