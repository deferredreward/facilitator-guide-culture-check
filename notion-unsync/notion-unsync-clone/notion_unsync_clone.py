#!/usr/bin/env python3
"""
Clone the content of a Notion synced block (reference) into normal, non-synced blocks.
This *simulates* "unsync" by copying the original synced content to a destination.
"""

import os
import time
import argparse
from typing import List, Dict, Any, Optional
from pathlib import Path

from notion_client import Client
from notion_client.errors import APIResponseError

# Load environment variables from parent directory .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")
TOKEN = os.environ.get("NOTION_API_KEY")  # required


def backoff_sleep(attempt: int) -> None:
    # Simple exponential backoff capping at ~10s
    delay = min(10, 0.5 * (2 ** attempt))
    time.sleep(delay)


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i+size]


def get_client() -> Client:
    if not TOKEN:
        raise RuntimeError("Missing NOTION_API_KEY env var.")
    return Client(auth=TOKEN, notion_version=NOTION_VERSION)


def retrieve_block(notion: Client, block_id: str) -> Dict[str, Any]:
    attempt = 0
    while True:
        try:
            return notion.blocks.retrieve(block_id=block_id)
        except APIResponseError as e:
            if e.status == 429:
                backoff_sleep(attempt); attempt += 1; continue
            # Re-raise all other errors (including 404) to be handled by caller
            raise


def list_children(notion: Client, block_id: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    start_cursor = None
    attempt = 0
    while True:
        try:
            resp = notion.blocks.children.list(block_id=block_id, start_cursor=start_cursor, page_size=100)
            results.extend(resp.get("results", []))
            start_cursor = resp.get("next_cursor")
            if not start_cursor:
                break
            attempt = 0  # reset upon success
        except APIResponseError as e:
            if e.status == 429:
                backoff_sleep(attempt); attempt += 1; continue
            raise
    return results


def block_to_create_payload(b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a retrieved block 'b' into a creation payload for append.
    We keep only the inner type payload (e.g., paragraph, heading_2, etc.).
    """
    t = b.get("type")
    if not t:
        return {"type": "paragraph", "paragraph": {"rich_text": []}}

    # Start with the type payload as-is
    inner = dict(b.get(t, {}))

    # Remove fields that would cause validation errors if present
    for k in ("id", "created_time", "last_edited_time", "created_by", "last_edited_by", "object", "archived", "in_trash"):
        inner.pop(k, None)

    # Avoid recreating a synced reference
    if t == "synced_block":
        # We do not recreate a 'synced_block' node itself to avoid sync linkage.
        # We'll return a placeholder container (toggle) and put its *children* later.
        return {"type": "toggle", "toggle": {"rich_text": [], "color": "default"}}

    return {"type": t, t: inner}


def fetch_children_deep(notion: Client, source_block_id: str) -> List[Dict[str, Any]]:
    """
    Recursively fetch children under source_block_id, following nested synced references.
    Returns a list of creation payloads; each payload may include its own 'children' list.
    """
    out: List[Dict[str, Any]] = []
    for b in list_children(notion, source_block_id):
        payload = block_to_create_payload(b)

        # Determine where to read this block's children from
        child_source_id: Optional[str] = None
        if b.get("has_children"):
            if b.get("type") == "synced_block":
                sb = b.get("synced_block", {})
                sf = sb.get("synced_from")
                if sf and sf.get("type") == "block_id" and sf.get("block_id"):
                    # For a *reference* synced block, dive into its original
                    child_source_id = sf["block_id"]
                else:
                    # For an *original* synced block (synced_from == null), its children are under b.id
                    child_source_id = b.get("id")
            else:
                child_source_id = b.get("id")

        if child_source_id:
            payload["children"] = fetch_children_deep(notion, child_source_id)

        out.append(payload)
    return out


def append_children(notion: Client, destination_id: str, children: List[Dict[str, Any]], dry_run: bool = False) -> None:
    if dry_run:
        # Print a compact preview
        import json
        print(json.dumps({"would_append": len(children)}, indent=2))
        return

    for group in chunks(children, 50):
        attempt = 0
        while True:
            try:
                notion.blocks.children.append(block_id=destination_id, children=group)
                break
            except APIResponseError as e:
                if e.status == 429:
                    backoff_sleep(attempt); attempt += 1; continue
                raise


def detach_synced_reference(reference_block_id: str, destination_id: str, dry_run: bool = False) -> None:
    notion = get_client()

    ref = retrieve_block(notion, reference_block_id)
    if ref.get("type") != "synced_block" or not ref.get("synced_block", {}).get("synced_from"):
        raise ValueError("Provided block is not a synced *reference* (missing synced_from).")

    source_id = ref["synced_block"]["synced_from"]["block_id"]
    
    # Check if the original block exists
    try:
        original_block = retrieve_block(notion, source_id)
        print(f"Found original block: {source_id}")
    except APIResponseError as e:
        if e.status == 404:
            print(f"ERROR: Original block {source_id} not found (404). This is an orphaned synced reference.")
            print("Cannot clone content from a non-existent original block.")
            return
        else:
            raise
    
    # Pull all children (deep) rooted at the original
    try:
        children_payloads = fetch_children_deep(notion, source_id)
    except APIResponseError as e:
        if e.status == 404:
            print(f"ERROR: Cannot access children of original block {source_id} (404).")
            print("The original block exists but its children are not accessible.")
            return
        else:
            raise

    if not children_payloads:
        print("No children found at the original source.")
        return

    append_children(notion, destination_id, children_payloads, dry_run=dry_run)
    print(f"Cloned {len(children_payloads)} top-level blocks into destination.")


def main():
    p = argparse.ArgumentParser(description="Clone a Notion synced block's source content to break sync by copy.")
    p.add_argument("--reference-block-id", dest="ref", required=True, help="The synced *reference* block id.")
    p.add_argument("--destination-id", dest="dest", required=True, help="Destination page or block id to append to.")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing to Notion.")
    args = p.parse_args()

    detach_synced_reference(args.ref, args.dest, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
