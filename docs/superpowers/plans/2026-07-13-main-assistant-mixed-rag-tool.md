# Main Assistant Mixed RAG Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the existing main-assistant knowledge-base tool use ProcessGen mixed RAG search when an image path is supplied.

**Architecture:** Keep one registered `tool_query_knowledge_base` and add an optional `image_path`. Route text-only calls to `rag_search_text` and image calls to `rag_search_mixed`, then reuse the existing result normalization.

**Tech Stack:** Python 3.11, AgentScope, pytest, pytest-asyncio

## Global Constraints

- Preserve all existing text-only calls.
- Do not add a second public RAG query tool.
- Keep the existing JSON result schema.
- Use the existing `_APIRequester`; do not access a database.

---

### Task 1: Add optional mixed retrieval to the main-assistant RAG tool

**Files:**
- Modify: `plugins/agent_extensions/__init__.py:1086-1138`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: `tool_query_knowledge_base(query, collection_name="process", limit=5, image_path="")`.
- Produces: `_query_knowledge_base_async(query, collection_name, limit, image_path=None)`.

- [ ] **Step 1: Write failing routing and registration tests**

Add tests asserting that `tool_query_knowledge_base` remains in `get_all_tools()`, text-only calls await `rag_search_text`, and calls with `image_path="query.png"` await:

```python
requester.rag_search_mixed.assert_awaited_once_with(
    "process", "堵盖", "query.png", limit=3
)
```

Patch `_run_async` for the synchronous entry test and assert it passes the image path into `_query_knowledge_base_async`.

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -q`

Expected: FAIL because the public and async methods do not accept `image_path`, and the async method always calls text search.

- [ ] **Step 3: Implement the minimal compatible routing**

Change the public method and async implementation to:

```python
def tool_query_knowledge_base(
    self, query, collection_name="process", limit=5, image_path=""
):
    result = _run_async(
        self._query_knowledge_base_async(
            query, collection_name, limit, image_path or None
        )
    )

async def _query_knowledge_base_async(
    self, query, collection_name, limit, image_path=None
):
    requester = self._get_requester()
    if image_path:
        search_results = await requester.rag_search_mixed(
            collection_name, query, image_path, limit=limit
        )
    else:
        search_results = await requester.rag_search_text(
            collection_name, query, limit=limit
        )
```

Keep the current result mapping and tool-level exception conversion unchanged. Update the docstring to expose the optional image path to AgentScope.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_agent_extensions_rag.py -q
.venv\Scripts\python.exe -m compileall -q plugins\agent_extensions tests\test_agent_extensions_rag.py
git diff --check
```

Expected: all focused tests PASS; compile and diff checks exit 0.

## Plan Self-Review

- The public signature, async signature, tests, and documented mixed endpoint use the same parameter order.
- Text-only behavior is explicitly retained.
- No placeholder or management functionality is included.
