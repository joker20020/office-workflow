# RAG Image Local Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task by task.

**Goal:** Download every RAG image through the new collection-scoped backend endpoint, overwrite a collision-safe local cache on every retrieval, and consume only the local file during reranking and AgentScope message construction.

**Architecture:** Extend `_APIRequester` with collection-aware image download and a general-image fallback used only after a 404. Thread `collection_name` through caching and reranking, degrade only double-404 candidates to text, and keep other backend failures visible.

**Tech stack:** Python 3.11, aiohttp, AgentScope 1.0.17, pytest, ProcessGen HTTP API.

## Constraints

- Primary endpoint: `GET /api/v1/rag/collections/{name}/asset?path=...`.
- Fallback endpoint: `GET /api/v1/images/{filename}`, only after primary HTTP 404.
- Do not fallback on authentication failures, 5xx responses, or transport errors.
- Download and overwrite on every call; do not reuse an existing cached file without requesting it again.
- Include collection name and asset path in cache identity.
- Reranking and AgentScope image blocks read only `_local_asset_path`.
- Treat `asset_path` as preferred and documented image `path` as compatibility fallback.
- A double 404 degrades only that candidate to text and preserves its original score.
- Preserve timeout work and unrelated worktree/index changes.
- Live verification is read-only against the backend and writes only to a temporary local directory.

## Task 1: Implement collection-scoped download and fallback

**Files:**

- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py`

- [ ] Add failing tests for `_APIRequester.rag_get_asset(collection_name, asset_path)`:
  - percent-encoded collection endpoint and unmodified query parameter;
  - primary 404 falls back to `/images/{quoted basename}`;
  - non-404 failure does not fall back;
  - double 404 raises `FileNotFoundError` containing collection and path.
- [ ] Run:

  ```powershell
  .venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -k "rag_asset" -q
  ```

  Confirm RED because the current method accepts only `asset_path` and calls the old endpoint.
- [ ] Implement `rag_get_asset(collection_name, asset_path)` using `_collection_name` for URL encoding.
- [ ] On primary 404 only, derive `os.path.basename(asset_path.replace("\\", "/"))` and request the percent-encoded general-image URL.
- [ ] Raise `FileNotFoundError` for an invalid basename or double 404; retain `_response_bytes` behavior for every other failure.
- [ ] Re-run the focused tests and confirm GREEN.

## Task 2: Make cache overwrite and isolation explicit

**Files:**

- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py`

- [ ] Add failing tests showing `_cache_rag_asset(collection_name, asset_path)`:
  - invokes `rag_get_asset` on every call;
  - overwrites an existing file with newly downloaded bytes;
  - returns different cache paths for identical asset paths in different collections;
  - produces filenames based on `sha256(collection_name + "\\0" + asset_path)` plus a safe basename.
- [ ] Run:

  ```powershell
  .venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -k "asset_cache" -q
  ```

  Confirm RED under the old signature/key.
- [ ] Implement the collection-aware key and unconditional binary overwrite under `data/img`.
- [ ] Re-run the focused tests and confirm GREEN.

## Task 3: Propagate collection context and degrade missing images safely

**Files:**

- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py`

- [ ] Update rerank tests to call `_rerank_rag_candidates(task, collection_name, candidates)` and assert collection propagation to the cache.
- [ ] Add failing tests for:
  - using `path` when `asset_path` is absent;
  - recording `_local_asset_path` after successful download;
  - catching only `FileNotFoundError`, recording `_asset_error`, preserving the score, and skipping image rerank;
  - allowing non-404/runtime failures to propagate;
  - `_process_agent_async` passing `collection_name` into reranking.
- [ ] Run:

  ```powershell
  .venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -k "rerank or process_agent" -q
  ```

  Confirm RED for the old signatures and failure behavior.
- [ ] Implement the new rerank signature and call site.
- [ ] Prefer `candidate["asset_path"]`, fall back to `candidate["path"]`, and warn accurately if neither exists.
- [ ] Catch only `FileNotFoundError` per candidate, store its text in `_asset_error`, preserve the original score, and continue processing other candidates.
- [ ] Leave all other exceptions uncaught.
- [ ] Re-run the focused tests and confirm GREEN.

## Task 4: Enforce local-only AgentScope image consumption

**Files:**

- Modify: `tests/test_agent_extensions_rag.py`
- Modify: `plugins/agent_extensions/__init__.py`

- [ ] Strengthen content-block tests with a recording loader to prove it receives only `_local_asset_path` values.
- [ ] Verify a candidate with `_asset_error` still contributes text but creates no image block.
- [ ] Remove the misleading `asset_path` warning from `_build_rag_content_blocks`; if no local cache exists and no prior error was recorded, warn that a local cache is unavailable.
- [ ] Add an assertion that the exact old warning text is absent from source.
- [ ] Run the complete focused test file:

  ```powershell
  .venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -q
  ```

## Task 5: Verify syntax, live behavior, and change scope

**Files:**

- Verify: `plugins/agent_extensions/__init__.py`
- Verify: `tests/test_agent_extensions_rag.py`

- [ ] Run syntax and whitespace checks:

  ```powershell
  .venv\Scripts\python.exe -m py_compile plugins\agent_extensions\__init__.py
  git -c safe.directory=E:/GitHub/office-workflow diff --check -- plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
  ```

- [ ] Run a read-only live probe against `http://192.168.1.5:8050/api/v1` in a temporary local directory:
  1. download `process/1783937076_0.png` through the collection endpoint;
  2. cache it, replace the file contents with `b"stale"`, cache it again, and verify fresh bytes overwrite the sentinel;
  3. request legacy `process/反推堵盖2.png` and verify primary 404/general-image fallback succeeds;
  4. construct content blocks from both `_local_asset_path` values and verify two image blocks are produced;
  5. make no backend writes.
- [ ] Inspect only the scoped diff and status:

  ```powershell
  git -c safe.directory=E:/GitHub/office-workflow diff -- plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
  git -c safe.directory=E:/GitHub/office-workflow status --short
  ```

- [ ] Use `superpowers:requesting-code-review` for a read-only review of endpoint correctness, 404-only fallback, overwrite behavior, cache isolation, candidate degradation, and local-only consumption.
- [ ] Apply technically valid review feedback using `superpowers:receiving-code-review`, then rerun all verification commands.
- [ ] Report test counts, live-probe evidence, and touched files without staging or committing implementation changes unless requested.
