# Artifact Sidebar Binary Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the artifact sidebar fully shown or hidden only through the chat header button, without removing width adjustment while it is shown.

**Architecture:** `ArtifactSidebar` becomes a pure expanded artifact list and owns its themed visual hierarchy. `ChatPanel` owns visibility and splitter-size restoration, retaining the last valid sidebar width and constraining the splitter to prevent accidental near-zero widths.

**Tech Stack:** Python 3.11, PySide6, pytest, existing `Theme` and Qt `QSplitter`.

## Implementation status

- [x] Removed the internal compact toggle and 36 px intermediate state.
- [x] Added header-button visibility toggling with constrained, restorable splitter width.
- [x] Applied a dedicated semantic theme hierarchy to the artifact list.
- [x] Verified with targeted tests, dark/light screenshots, and the full test suite.

## Global Constraints

- Do not change artifact persistence, path safety, opening, reveal, copy, or session behavior.
- The Artifact header button is the only show/hide control.
- Keep the artifact splitter handle draggable while visible.
- Use semantic `Theme` styles in dark and light themes.

---

### Task 1: Cover binary visibility and theme behavior

**Files:**

- Modify: `src/ui/chat/artifact_sidebar.py`
- Modify: `src/ui/chat/chat_panel.py`
- Modify: `tests/test_artifact_sidebar.py`
- Modify: `tests/test_chat_panel.py`

**Interfaces:**

- `ChatPanel._toggle_artifact_sidebar()` hides or shows the sidebar.
- `ChatPanel._artifact_sidebar_width` stores the last width that meets the sidebar minimum.

- [ ] Write failing tests showing that the sidebar has no `_collapse_button`, is hidden or shown only by the header button, and restores a width at or above its minimum.
- [ ] Run `uv run pytest tests/test_artifact_sidebar.py tests/test_chat_panel.py -q` and confirm the tests fail because the 36 px state remains.
- [ ] Remove the sidebar header toggle and compact-state sizing. Implement header-button visibility toggling, valid-width capture from the splitter, and restoration to the last valid or default width.
- [ ] Give the sidebar root an `artifactSidebar` selector and rebuild its scroll, sections, cards, labels, and compact action buttons on every theme refresh using semantic `Theme` colors.
- [ ] Run `uv run pytest tests/test_artifact_sidebar.py tests/test_chat_panel.py -q` and confirm it passes.

### Task 2: Verify resizing limits and visual refresh

**Files:**

- Modify: `src/ui/theme.py` if a sidebar-specific style helper is needed.
- Modify: `tests/test_ui_layout.py`

**Interfaces:**

- The visible sidebar remains draggable only between its readable minimum and maximum widths.
- `Theme.get_artifact_sidebar_stylesheet()` returns the root sidebar style if needed.

- [ ] Write a failing dark/light test that asserts the root uses the `QFrame#artifactSidebar` selector and semantic background color after `refresh_theme()`.
- [ ] Run `uv run pytest tests/test_ui_layout.py -q` and confirm it fails against the current generic card root style.
- [ ] Add the minimal sidebar-specific `Theme` helper and apply it during construction and `refresh_theme()`.
- [ ] Run `uv run ruff check src/ui/chat/artifact_sidebar.py src/ui/chat/chat_panel.py tests/test_artifact_sidebar.py tests/test_chat_panel.py tests/test_ui_layout.py` and `uv run pytest -q`; confirm all checks and tests pass.
