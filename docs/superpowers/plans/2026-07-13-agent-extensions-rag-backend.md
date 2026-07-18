# Agent Extensions RAG Backend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every `agent_extensions` RAG operation through the ProcessGen `/api/v1/rag/*` HTTP API and remove all direct Milvus access.

**Architecture:** Extend the existing `_APIRequester` in `plugins/agent_extensions/__init__.py` with the documented RAG endpoints. Runtime tools consume the backend's standard search result objects, while `populate_rag.py` uploads source files and delegates chunking, embedding, and persistence to the backend.

**Tech Stack:** Python 3.11, aiohttp, pytest, pytest-asyncio, AgentScope

## Global Constraints

- Use `RAG_BASE_URL`, defaulting to `http://localhost:8050/api/v1`.
- Do not connect to Milvus or retain `pymilvus`, `MilvusClient`, `MoyuClient`, or `MILVUS_BASE_URL` references.
- Use `POST /api/v1/rag/collections/{name}/search/mixed` when both task text and an image are supplied.
- Delete unsupported raw-vector CRUD APIs without compatibility placeholders.
- Preserve the user's existing `backend-README.md` and image-generation prompt edits.

---

## File Structure

- Modify `plugins/agent_extensions/__init__.py`: add RAG HTTP methods, remove `_MoyuClient`, and migrate both runtime RAG flows.
- Modify `plugins/agent_extensions/populate_rag.py`: upload source files through `_APIRequester` and demonstrate backend search.
- Delete `plugins/agent_extensions/moyus_client.py`: remove the direct Milvus client.
- Delete `plugins/agent_extensions/demo_moyu_client.py`: remove the obsolete CRUD demo.
- Replace `tests/test_moyu_client.py` with `tests/test_agent_extensions_rag.py`: cover HTTP contracts and migrated retrieval helpers.
- Modify `pyproject.toml`: remove `pymilvus`.

### Task 1: Add the backend RAG HTTP contract to `_APIRequester`

**Files:**
- Modify: `plugins/agent_extensions/__init__.py:89-220`
- Create: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Produces: `rag_create_collection`, `rag_list_collections`, `rag_delete_collection`, `rag_add_text`, `rag_add_images`, `rag_search_text`, `rag_search_image`, `rag_search_mixed`, `rag_list_entities`, `rag_delete_entity`, and `rag_get_asset` asynchronous methods on `_APIRequester`.
- Produces: search methods returning `List[Dict[str, Any]]`, extracted from the backend `results` field.

- [ ] **Step 1: Write failing tests for URL normalization, JSON collection requests, text search, and mixed search**

Create `tests/test_agent_extensions_rag.py` with a small async context-manager response/session fake. Patch `aiohttp.ClientSession` and `aiohttp.FormData`; assert that:

```python
@pytest.mark.asyncio
async def test_rag_search_text_uses_backend_query_params(requester, fake_session):
    fake_session.queue_json({"results": [{"id": 1, "score": 0.8, "type": "text"}]})
    result = await requester.rag_search_text("process", "堵盖", limit=3, subject="capp")
    assert result == [{"id": 1, "score": 0.8, "type": "text"}]
    assert fake_session.last_request == (
        "GET",
        "http://backend/api/v1/rag/collections/process/search",
        {"params": {"query": "堵盖", "limit": 3, "subject": "capp"}},
    )

@pytest.mark.asyncio
async def test_rag_search_mixed_posts_query_image_and_limit(requester, fake_session, tmp_path):
    image = tmp_path / "query.png"
    image.write_bytes(b"png")
    fake_session.queue_json({"results": []})
    assert await requester.rag_search_mixed("process", "堵盖", str(image), 5) == []
    method, url, kwargs = fake_session.last_request
    assert method == "POST"
    assert url == "http://backend/api/v1/rag/collections/process/search/mixed"
    assert kwargs["data"].fields["query"] == "堵盖"
    assert kwargs["data"].fields["limit"] == "5"
    assert kwargs["data"].fields["image"][1] == "query.png"
```

Also assert `base_url="http://backend/api/v1/"` becomes `http://backend/api/v1`, collection creation posts `{"collection_name": name}`, and a response whose `results` is missing or not a list raises `RuntimeError("RAG 后端响应格式无效: results 必须为列表")`.

- [ ] **Step 2: Run the new contract tests and verify RED**

Run: `python -m pytest tests/test_agent_extensions_rag.py -q`

Expected: FAIL because `_APIRequester` has no `rag_search_text` or `rag_search_mixed` methods and does not normalize `base_url`.

- [ ] **Step 3: Implement the RAG methods minimally**

In `_APIRequester.__init__`, set `self.base_url = base_url.rstrip("/")`. Add a shared status helper and endpoint methods following this shape:

```python
async def _response_json(self, response, operation: str) -> Dict[str, Any]:
    if response.status < 200 or response.status >= 300:
        detail = await response.text()
        raise RuntimeError(f"{operation}失败: HTTP {response.status} - {detail}")
    return await response.json()

def _search_results(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise RuntimeError("RAG 后端响应格式无效: results 必须为列表")
    return results

async def rag_create_collection(self, collection_name: str) -> Dict[str, Any]:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{self.base_url}/rag/collections",
            json={"collection_name": collection_name},
        ) as response:
            return await self._response_json(response, "创建 RAG 集合")

async def rag_search_text(self, collection_name, query, limit=10, subject=None):
    import aiohttp
    params = {"query": query, "limit": limit}
    if subject is not None:
        params["subject"] = subject
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{self.base_url}/rag/collections/{collection_name}/search",
            params=params,
        ) as response:
            payload = await self._response_json(response, "RAG 文本检索")
    return self._search_results(payload)

async def rag_search_mixed(
    self, collection_name, query, image_path, limit=10, subject=None
):
    import aiohttp
    data = aiohttp.FormData()
    data.add_field("query", query)
    data.add_field("limit", str(limit))
    if subject is not None:
        data.add_field("subject", subject)
    with open(image_path, "rb") as image_file:
        data.add_field(
            "image",
            image_file,
            filename=os.path.basename(image_path),
            content_type=self._image_content_type(image_path),
        )
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rag/collections/{collection_name}/search/mixed",
                data=data,
            ) as response:
                payload = await self._response_json(response, "RAG 混合检索")
    return self._search_results(payload)
```

Implement the remaining documented methods with the same response handling. `rag_add_text` sends multipart `file` and optional `subject`; `rag_add_images` validates equal nonzero list lengths and adds repeated `images` and `descriptions` fields; `rag_search_image` posts `image`, `limit`, and optional `subject`; entity listing uses `offset` and `limit` query parameters; asset retrieval uses `params={"path": asset_path}` and returns response bytes.

- [ ] **Step 4: Run the contract tests and verify GREEN**

Run: `python -m pytest tests/test_agent_extensions_rag.py -q`

Expected: PASS for all Task 1 tests.

- [ ] **Step 5: Commit the HTTP contract**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "feat: add ProcessGen RAG API client methods"
```

### Task 2: Migrate knowledge retrieval and process-agent candidate selection

**Files:**
- Modify: `plugins/agent_extensions/__init__.py:482-1078`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Consumes: `_APIRequester.rag_search_text`, `_APIRequester.rag_search_mixed`, `_APIRequester.rag_get_asset`, and `_APIRequester.query_rerank`.
- Produces: `AgentExtensionTools._search_rag_candidates(task, image_path, collection_name, limit)`.
- Produces: `AgentExtensionTools._rerank_rag_candidates(task, candidates)` returning candidates sorted by final `score`.

- [ ] **Step 1: Write failing tests for text/mixed routing, response mapping, and rerank fallback**

Use an `AsyncMock` requester injected as `tools._requester`. Add tests equivalent to:

```python
@pytest.mark.asyncio
async def test_search_candidates_uses_mixed_endpoint_when_image_is_present():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.rag_search_mixed.return_value = [{"id": 1, "score": 0.6}]
    result = await tools._search_rag_candidates("堵盖", "query.png", "process", 5)
    assert result == [{"id": 1, "score": 0.6}]
    tools._requester.rag_search_mixed.assert_awaited_once_with(
        "process", "堵盖", "query.png", 5
    )
    tools._requester.rag_search_text.assert_not_awaited()

@pytest.mark.asyncio
async def test_rerank_failure_keeps_original_rag_score():
    tools = AgentExtensionTools()
    tools._requester = AsyncMock()
    tools._requester.query_rerank.side_effect = RuntimeError("offline")
    candidates = [{"id": 1, "score": 0.42, "type": "text", "text": "内容"}]
    result = await tools._rerank_rag_candidates("问题", candidates)
    assert result[0]["score"] == 0.42
```

Add coverage for no-image text routing, image candidates fetched through `asset_path`, descending rerank order, and `_query_knowledge_base_async` returning `id`, rounded `score`, `text` limited to 500 characters, `path`, `type`, `subject`, and `asset_path`.

- [ ] **Step 2: Run the retrieval tests and verify RED**

Run: `python -m pytest tests/test_agent_extensions_rag.py -q`

Expected: FAIL because `_search_rag_candidates` and `_rerank_rag_candidates` do not exist and knowledge lookup still constructs `_MoyuClient`.

- [ ] **Step 3: Implement retrieval helpers and remove `_MoyuClient`**

Delete the complete `_MoyuClient` class. Add helpers on `AgentExtensionTools`:

```python
async def _search_rag_candidates(self, task, image_path, collection_name, limit):
    requester = self._get_requester()
    if image_path:
        return await requester.rag_search_mixed(
            collection_name, task, image_path, limit
        )
    return await requester.rag_search_text(collection_name, task, limit)

async def _rerank_rag_candidates(self, task, candidates):
    requester = self._get_requester()
    ranked = []
    for candidate in candidates:
        item = dict(candidate)
        try:
            if item.get("type") == "image" and item.get("asset_path"):
                image_path = await self._cache_rag_asset(item["asset_path"])
                response = await requester.query_rerank(
                    "text", task, None, "image", None, image_path
                )
            elif item.get("type") == "text":
                response = await requester.query_rerank(
                    "text", task, None, "text", item.get("text", ""), None
                )
            else:
                response = None
            if response is not None:
                item["score"] = response["score"]
        except Exception as exc:
            _logger.warning(f"RAG 候选重排失败，保留原始分数: {exc}")
        ranked.append(item)
    return sorted(ranked, key=lambda item: item.get("score", 0.0), reverse=True)
```

`_cache_rag_asset` must use `rag_get_asset(asset_path)`, derive a safe basename with `os.path.basename`, create `data/img`, write bytes, and return the local path. Change `_get_requester`'s default URL to port 8050.

Rewrite `_query_knowledge_base_async` to call `rag_search_text` directly and map the standard backend result fields. Update `_process_agent_async` to call the two helpers, slice to `limit`, and iterate the actual result list rather than `range(limit)`. Remove its embedding and Milvus steps. For image prompt blocks, read only the cached file returned from `asset_path`; if no `asset_path`, emit the text description and log a warning.

- [ ] **Step 4: Run retrieval tests and verify GREEN**

Run: `python -m pytest tests/test_agent_extensions_rag.py -q`

Expected: PASS, with no attempted `query_embedding` or Milvus construction.

- [ ] **Step 5: Commit the runtime migration**

```bash
git add plugins/agent_extensions/__init__.py tests/test_agent_extensions_rag.py
git commit -m "refactor: route agent RAG retrieval through backend"
```

### Task 3: Migrate the population script and remove obsolete clients

**Files:**
- Modify: `plugins/agent_extensions/populate_rag.py`
- Delete: `plugins/agent_extensions/moyus_client.py`
- Delete: `plugins/agent_extensions/demo_moyu_client.py`
- Delete: `tests/test_moyu_client.py`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Consumes: `_APIRequester` RAG collection, upload, and search methods.
- Produces: an executable population script requiring only ProcessGen at `RAG_BASE_URL`.

- [ ] **Step 1: Write a failing source-level migration test**

Add a test that reads the population script and asserts the new imports/configuration:

```python
def test_population_script_uses_backend_rag_api_only():
    source = Path("plugins/agent_extensions/populate_rag.py").read_text("utf-8")
    assert "from plugins.agent_extensions import _APIRequester" in source
    assert "rag_add_text" in source
    assert "rag_add_images" in source
    assert "MILVUS" not in source
    assert "MoyuClient" not in source
    assert "TextProcessor" not in source
```

- [ ] **Step 2: Run the migration test and verify RED**

Run: `python -m pytest tests/test_agent_extensions_rag.py::test_population_script_uses_backend_rag_api_only -q`

Expected: FAIL because the current script imports `MoyuClient`, `TextProcessor`, and Milvus configuration.

- [ ] **Step 3: Rewrite the script around `_APIRequester`**

Keep the existing example paths and collection name, but replace the main flow with:

```python
async def reset_collection(requester):
    collections = await requester.rag_list_collections()
    names = {item["name"] for item in collections.get("collections", [])}
    if COLLECTION_NAME in names:
        await requester.rag_delete_collection(COLLECTION_NAME)
    return await requester.rag_create_collection(COLLECTION_NAME)

async def upload_sources(requester):
    if MD_PATH.exists():
        await requester.rag_add_text(COLLECTION_NAME, str(MD_PATH), subject="capp")
    valid = [(path, text) for path, text in zip(IMAGE_PATHS, IMAGE_TEXTS) if path.exists()]
    if valid:
        await requester.rag_add_images(
            COLLECTION_NAME,
            [str(path) for path, _ in valid],
            [text for _, text in valid],
            subject="capp",
        )

async def main():
    requester = _APIRequester(base_url=RAG_BASE_URL)
    await reset_collection(requester)
    await upload_sources(requester)
    results = await requester.rag_search_text(
        COLLECTION_NAME, "加工内表面螺纹孔", limit=2
    )
    for item in results:
        print(f"- {item['id']}: {item.get('text', '')[:60]}")
```

Delete all local chunking, vector construction, filtering, and database calls. Delete the two obsolete client/demo modules and the old Milvus-centric test file.

- [ ] **Step 4: Run the migration tests and verify GREEN**

Run: `python -m pytest tests/test_agent_extensions_rag.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the script migration and deletions**

```bash
git add plugins/agent_extensions/populate_rag.py plugins/agent_extensions/moyus_client.py plugins/agent_extensions/demo_moyu_client.py tests/test_moyu_client.py tests/test_agent_extensions_rag.py
git commit -m "refactor: remove plugin Milvus client and CRUD demo"
```

### Task 4: Remove the dependency and verify the complete migration

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_agent_extensions_rag.py`

**Interfaces:**
- Consumes: all migrated code from Tasks 1-3.
- Produces: a plugin dependency graph with no database client.

- [ ] **Step 1: Add a failing repository migration assertion**

Add a test that searches only the in-scope production files and dependency manifest:

```python
def test_agent_extensions_has_no_direct_database_client():
    paths = [Path("plugins/agent_extensions"), Path("pyproject.toml")]
    forbidden = ("pymilvus", "MilvusClient", "MoyuClient", "MILVUS_BASE_URL")
    for path in paths:
        files = path.rglob("*.py") if path.is_dir() else [path]
        for file in files:
            source = file.read_text("utf-8")
            assert not any(token in source for token in forbidden), file
```

- [ ] **Step 2: Run the assertion and verify RED**

Run: `python -m pytest tests/test_agent_extensions_rag.py::test_agent_extensions_has_no_direct_database_client -q`

Expected: FAIL because `pyproject.toml` still contains `pymilvus`.

- [ ] **Step 3: Remove `pymilvus` from `pyproject.toml`**

Delete exactly the dependency line `"pymilvus>=2.6.12",`. Do not alter unrelated dependencies.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
python -m pytest tests/test_agent_extensions_rag.py -q
python -m pytest -q
rg -n "pymilvus|MilvusClient|MoyuClient|MILVUS_BASE_URL|MILVUS_URI" plugins/agent_extensions pyproject.toml
git diff --check
```

Expected: focused tests PASS; full suite PASS; `rg` exits 1 with no matches; `git diff --check` exits 0. If the full suite has a pre-existing environmental failure, record the exact failing test and confirm the focused suite remains green.

- [ ] **Step 5: Commit dependency cleanup**

```bash
git add pyproject.toml tests/test_agent_extensions_rag.py
git commit -m "chore: remove plugin Milvus dependency"
```

## Plan Self-Review

- Every design requirement is assigned to Tasks 1-4.
- Method names and result shapes are consistent across HTTP, runtime, script, and tests.
- Production changes follow RED-GREEN cycles before implementation.
- Existing unrelated worktree changes are explicitly preserved and excluded from task commits.
