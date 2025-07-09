#!/usr/bin/env python3
"""
AI Handler - Shared module for AI interactions

This module provides a unified interface for interacting with Claude, Gemini, and OpenAI models.
It can be imported and used by other scripts that need AI functionality.
"""

import os
import logging
from dotenv import load_dotenv
import anthropic
import google.generativeai as genai
import openai

# Load environment variables
load_dotenv()

class AIHandler:
    """Handler for AI model interactions"""
    
    def __init__(self, model_type='gemini'):
        """
        Initialize AI handler
        
        Args:
            model_type (str): 'claude', 'anthropic', 'gemini', or 'openai' (default: gemini)
        """
        self.model_type = model_type.lower()
        self.claude_client = None
        self.gemini_model = None
        self.openai_client = None
        
        # Initialize the selected model
        if self.model_type in ['claude', 'anthropic']:
            self._init_claude()
        elif self.model_type == 'openai':
            self._init_openai()
        else:
            self._init_gemini()
    
    def _init_claude(self):
        """Initialize Claude client"""
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            raise ValueError("CLAUDE_API_KEY not found in environment variables")
        
        try:
            # Try to initialize with default parameters first
            self.claude_client = anthropic.Anthropic(api_key=api_key)
            logging.info("✅ Claude client initialized successfully")
        except TypeError as e:
            # Handle version compatibility issues
            if "proxies" in str(e):
                logging.warning("⚠️ Claude client initialization failed due to version compatibility. Trying alternative initialization...")
                try:
                    # Try without any additional parameters
                    self.claude_client = anthropic.Anthropic(api_key=api_key)
                    logging.info("✅ Claude client initialized successfully (alternative method)")
                except Exception as e2:
                    logging.error(f"❌ Failed to initialize Claude client: {e2}")
                    logging.error("💡 Try updating the anthropic library: pip install --upgrade anthropic")
                    raise ValueError(f"Claude client initialization failed: {e2}")
            else:
                logging.error(f"❌ Failed to initialize Claude client: {e}")
                raise
        except Exception as e:
            logging.error(f"❌ Failed to initialize Claude client: {e}")
            logging.error("💡 Check your CLAUDE_API_KEY and try updating the anthropic library: pip install --upgrade anthropic")
            raise
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        try:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logging.info("✅ OpenAI client initialized successfully")
        except Exception as e:
            logging.error(f"❌ Failed to initialize OpenAI client: {e}")
            logging.error("💡 Check your OPENAI_API_KEY and try updating the openai library: pip install --upgrade openai")
            raise
    
    def _init_gemini(self):
        """Initialize Gemini model"""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        try:
            genai.configure(api_key=api_key)
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-preview-05-20')
            self.gemini_model = genai.GenerativeModel(model_name)
            logging.info(f"✅ Gemini model initialized successfully: {model_name}")
        except Exception as e:
            logging.error(f"❌ Failed to initialize Gemini model: {e}")
            logging.error("💡 Check your GEMINI_API_KEY and try updating the google-generativeai library: pip install --upgrade google-generativeai")
            raise
    
    def get_response(self, prompt, max_tokens=4000, temperature=0.3):
        """
        Get response from the selected AI model
        
        Args:
            prompt (str): The prompt to send to the AI
            max_tokens (int): Maximum tokens for response (Claude and OpenAI only)
            temperature (float): Temperature for response generation
            
        Returns:
            str: The AI response text
        """
        try:
            if self.model_type in ['claude', 'anthropic']:
                return self._get_claude_response(prompt, max_tokens, temperature)
            elif self.model_type == 'openai':
                return self._get_openai_response(prompt, max_tokens, temperature)
            else:
                return self._get_gemini_response(prompt, temperature)
        except Exception as e:
            logging.error(f"❌ Error getting AI response: {e}")
            raise
    
    def _get_claude_response(self, prompt, max_tokens, temperature):
        """Get response from Claude"""
        model = os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
        
        logging.info(f"🤖 Sending content to Claude ({model})...")
        
        try:
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            logging.info("✅ Received response from Claude")
            return response.content[0].text
        except Exception as e:
            logging.error(f"❌ Error with Claude API call: {e}")
            logging.error(f"💡 Check if the model '{model}' is available and your API key has access to it")
            raise
    
    def _get_openai_response(self, prompt, max_tokens, temperature):
        """Get response from OpenAI"""
        model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        
        logging.info(f"🤖 Sending content to OpenAI ({model})...")
        
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            logging.info("✅ Received response from OpenAI")
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"❌ Error with OpenAI API call: {e}")
            logging.error(f"💡 Check if the model '{model}' is available and your API key has access to it")
            raise
    
    def _get_gemini_response(self, prompt, temperature):
        """Get response from Gemini"""
        logging.info(f"🤖 Sending content to Gemini...")
        
        try:
            response = self.gemini_model.generate_content(prompt)
            
            logging.info("✅ Received response from Gemini")
            return response.text
        except Exception as e:
            logging.error(f"❌ Error with Gemini API call: {e}")
            raise

def create_ai_handler(model_type='gemini'):
    """
    Factory function to create an AI handler
    
    Args:
        model_type (str): 'claude', 'anthropic', 'gemini', or 'openai'
        
    Returns:
        AIHandler: Configured AI handler instance
    """
    return AIHandler(model_type) 