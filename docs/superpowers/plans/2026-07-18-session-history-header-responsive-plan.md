# Session History Header Responsive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the session-history title visible while the assistant's history rail is resized.

**Architecture:** `SessionListWidget` owns a two-layout header and switches layouts from its resize event. The title label and New Session button are moved between the horizontal and stacked layouts without recreating either widget.

**Tech Stack:** Python 3.11, PySide6, pytest, existing `SessionListWidget`.

## Implementation status

- [x] Added Chinese/English regression coverage at narrow and normal rail widths.
- [x] Implemented the responsive single-row / two-row header switch.
- [x] Removed the fixed new-session button width so its localized text remains visible.
- [x] Completed targeted checks and the full test suite.

## Global Constraints

- Preserve the draggable session rail and all session-selection behavior.
- Keep the full localized title and button text visible in `zh_CN` and `en`.
- Do not use a tooltip as a replacement for visible title text.

---

### Task 1: Add responsive-header regression coverage and implementation

**Files:**

- Modify: `tests/test_ui_layout.py`
- Modify: `src/ui/chat/chat_panel.py`

**Interfaces:**

- `SessionListWidget._update_header_layout()` switches the header between horizontal and stacked placements.
- `SessionListWidget._is_header_stacked` exposes the active layout state for regression coverage.

- [ ] Add a failing test that creates a `SessionListWidget`, resizes it to a narrow width, and asserts the title uses a full-width first row while the New Session button occupies a second row. Then resize it wider and assert the horizontal layout returns.
- [ ] Run `uv run pytest tests/test_ui_layout.py -q` and confirm it fails because the current header has only one layout.
- [ ] Implement a secondary header row, move the existing button between the rows at a measured title-plus-button breakpoint, and call the update method from resize, language refresh, and theme refresh paths.
- [ ] Run `uv run pytest tests/test_ui_layout.py tests/test_chat_panel.py -q` and confirm it passes.
- [ ] Run the full test suite and commit the implementation, tests, and design records.
