#!/usr/bin/env python3
"""
Batch Processing Script - Run orchestrator on multiple pages with different AI models

This script processes multiple Notion pages in succession, running the full orchestrator
workflow (ESL enhancement → Trainer questions → Cultural adaptations) with different AI models.
"""

import subprocess
import sys
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'batch_process_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

# Pages to process with their AI models
PAGES = [
    {
        "name": "Gemini Pro Page",
        "page_id": "25372d5af2de80b99157e291f353611b",
        "ai_model": "gemini"
    },
    {
        "name": "Claude 4 Sonnet Page", 
        "page_id": "25372d5af2de8076ba29fc9efd83c345",
        "ai_model": "claude"
    },
    {
        "name": "Grok 4 Page",
        "page_id": "25372d5af2de80e690b8fa0a8d0719b4", 
        "ai_model": "xai"
    }
]

def run_orchestrator(page_id, ai_model, page_name):
    """
    Run the orchestrator on a single page with specified AI model
    
    Args:
        page_id (str): Notion page ID
        ai_model (str): AI model to use
        page_name (str): Human-readable page name for logging
    
    Returns:
        bool: True if successful, False if failed
    """
    try:
        logging.info(f"Starting processing: {page_name} with {ai_model}")
        
        # Build command
        cmd = [sys.executable, "orchestrator.py", page_id, "--ai", ai_model]
        
        logging.info(f"Running command: {' '.join(cmd)}")
        
        # Run orchestrator with no timeout
        start_time = time.time()
        result = subprocess.run(
            cmd,
            cwd=".",
            capture_output=True,
            text=True
        )
        
        duration = time.time() - start_time
        duration_hours = duration / 3600
        
        if result.returncode == 0:
            logging.info(f"SUCCESS: {page_name} completed in {duration_hours:.1f}h")
            logging.info(f"Output: {result.stdout}")
            return True
        else:
            logging.error(f"FAILED: {page_name} failed with return code {result.returncode}")
            logging.error(f"Error output: {result.stderr}")
            logging.error(f"Stdout: {result.stdout}")
            return False
    except Exception as e:
        logging.error(f"EXCEPTION: {page_name} failed with error: {e}")
        return False

def main():
    """Main batch processing function"""
    logging.info("Starting batch processing of Notion pages")
    logging.info(f"Processing {len(PAGES)} pages total")
    
    start_time = time.time()
    results = []
    
    for i, page_info in enumerate(PAGES, 1):
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing page {i}/{len(PAGES)}: {page_info['name']}")
        logging.info(f"AI Model: {page_info['ai_model']}")
        logging.info(f"Page ID: {page_info['page_id']}")
        logging.info(f"{'='*60}")
        
        success = run_orchestrator(
            page_info['page_id'],
            page_info['ai_model'], 
            page_info['name']
        )
        
        results.append({
            'name': page_info['name'],
            'ai_model': page_info['ai_model'],
            'success': success
        })
        
        # Brief pause between pages
        if i < len(PAGES):
            logging.info("Pausing 10 seconds before next page...")
            time.sleep(10)
    
    # Summary report
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    logging.info(f"\n{'BATCH PROCESSING COMPLETE' if failed == 0 else 'BATCH PROCESSING FINISHED WITH ERRORS'}")
    logging.info(f"Total processing time: {total_time/60:.1f} minutes")
    logging.info(f"Successful: {successful}/{len(PAGES)}")
    logging.info(f"Failed: {failed}/{len(PAGES)}")
    
    logging.info("\nDETAILED RESULTS:")
    for result in results:
        status = "SUCCESS" if result['success'] else "FAILED"
        logging.info(f"  {status}: {result['name']} ({result['ai_model']})")
    
    if failed > 0:
        logging.warning(f"\n{failed} page(s) failed. Check the logs above for details.")
        sys.exit(1)
    else:
        logging.info("\nAll pages processed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("\nBatch processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"\nBatch processing failed with unexpected error: {e}")
        sys.exit(1)