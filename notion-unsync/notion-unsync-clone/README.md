# Notion “Unsync” (Clone Synced Block Content) — Python

This package shows how to **simulate** “unsyncing” a Notion Synced Block using the API by **cloning the source content** of a reference synced block into a normal, non‑synced set of blocks.

> ⚠️ There is no Notion API to “unsync” a Synced Block. The Notion UI can do it. With the API, you can only **copy** the content so future edits won’t propagate.

## What this does

- Accepts a **reference synced block id** (the block that shows `synced_from`).
- Resolves the **original block** via `synced_from.block_id`.
- Recursively pulls the original’s **children** (following nested synced blocks too).
- Appends those blocks under a **destination page or block** as **non‑synced** content.

## Requirements

- Python 3.9+
- A Notion internal integration token with access to both the **reference** and **original** blocks and the **destination**.
- Install deps:
  ```bash
  pip install notion-client python-dotenv
  ```

## Quick start

1) Set your token (e.g., via env var or `.env`):
```bash
export NOTION_TOKEN="secret_..."
```

2) Run the script:
```bash
python notion_unsync_clone.py \
  --reference-block-id 25c72d5a-f2de-8171-ae93-f61df1e22377 \
  --destination-id     YOUR_DESTINATION_PAGE_OR_BLOCK_ID
```

> The reference id above matches your example JSON. Replace the destination id with a page or block where you want the cloned content to appear.

## Notes & tips

- **Pagination** is handled (page_size=100 with cursors).
- **Rate limits (429)**: minimal retry logic included.
- **Chunked appends**: sends up to 50 blocks per request.
- **Field cleanup**: converts retrieved blocks into creation payloads (drops read‑only, strips `synced_from`, etc.).
- **Nested synced blocks**: if it sees a nested *reference* synced block, it follows its `synced_from` and inlines that content.
- **Block types**: most blocks can be re-posted directly from the `retrieve`/`children.list` payload’s inner `<class 'type'>` object, but we defensively remove stray properties if present.

## CLI

```text
usage: notion_unsync_clone.py [-h] --reference-block-id REF --destination-id DEST [--dry-run]
```

- `--dry-run`: Prints what would be appended without writing to Notion.

## Safety

- This script **does not delete** or alter your original blocks.
- It **creates** new blocks under the destination, leaving the synced relationship untouched elsewhere.

---

© 2025 — Example code for educational use.
