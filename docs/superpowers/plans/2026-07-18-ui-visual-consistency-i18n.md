# UI Visual Consistency and Multilingual Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the PySide6 interface visually consistent across all primary pages while ensuring Chinese and English labels remain readable without clipping.

**Architecture:** Keep `Theme` as the single source of visual tokens and add compact layout/control helpers there. Page widgets consume those helpers and translation keys; a focused layout test module builds representative widgets under both locales and validates visible controls against Qt font metrics.

**Tech Stack:** Python 3.11, PySide6, PyYAML, pytest, existing `ThemeAwareMixin` and `LanguageAwareMixin`.

## Implementation status

- [x] Shared visual tokens, responsive controls, and clipped-text tooltips implemented.
- [x] Primary workspace and artifact sidebar localized and visually unified.
- [x] Plugin/package management views and installation dialogs made layout-driven.
- [x] Chinese/English and dark/light visual checks completed; full test suite passed.

## Global Constraints

- Keep the current navigation and application behavior unchanged.
- Preserve dark/light themes and the graphite/indigo visual identity.
- Support `zh_CN` and `en` at 800×600 and representative desktop width.
- Do not change artifact, workflow, agent, or session persistence behavior.
- Use translation keys for all newly touched static UI copy.
- Preserve unrelated user working-tree changes; stage only files listed by each task.

## File structure

- `src/ui/theme.py`: shared geometry tokens and QSS helpers for panels, cards, compact buttons, icons, and focus states.
- `src/ui/layout_utils.py`: helpers that detect clipped widget text and expose an accessible full-text tooltip only when a compact label is elided.
- `src/ui/navigation_rail.py`, `src/ui/home_page.py`, `src/ui/chat/chat_panel.py`, `src/ui/chat/artifact_sidebar.py`: primary workspace presentation.
- `src/ui/plugins/plugin_panel.py`, `src/ui/packages/package_panel.py`, `src/ui/settings/settings_panel.py`, `src/ui/plugins/permission_dialog.py`: management pages and dialogs.
- `resources/translations/zh_CN.yaml`, `resources/translations/en.yaml`: labels for all touched UI controls.
- `tests/test_theme.py`, `tests/test_artifact_sidebar.py`, `tests/test_ui_layout.py`: token, localization, and geometry regression coverage.

---

### Task 1: Establish shared visual and clipping primitives

**Files:**

- Create: `src/ui/layout_utils.py`
- Modify: `src/ui/theme.py`
- Modify: `tests/test_theme.py`
- Create: `tests/test_ui_layout.py`

**Interfaces:**

- Produces `apply_elision_tooltip(widget: QLabel | QPushButton) -> None`. It preserves explicit tooltips and otherwise exposes full text only when `QFontMetrics.elidedText` differs from widget text.
- Produces `Theme.METRICS` with `control_height`, `compact_control_height`, `page_margin`, `section_gap`, and `card_radius`.
- Produces `Theme.get_card_stylesheet()` and `Theme.get_compact_button_stylesheet(kind: str = "default")`.

- [ ] **Step 1: Write failing token and tooltip tests**

```python
def test_theme_exposes_shared_geometry_tokens():
    assert Theme.METRICS["control_height"] >= 28
    assert Theme.METRICS["page_margin"] >= Theme.METRICS["section_gap"]


def test_elision_tooltip_exposes_full_text_only_when_clipped(qapp):
    label = QLabel("A translated label that cannot fit in this narrow row")
    label.resize(20, 24)
    apply_elision_tooltip(label)
    assert label.toolTip() == label.text()
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/test_theme.py tests/test_ui_layout.py -q`

Expected: FAIL because `Theme.METRICS`, `src.ui.layout_utils`, and `apply_elision_tooltip` do not exist.

- [ ] **Step 3: Write the minimal implementation**

```python
def apply_elision_tooltip(widget):
    if widget.toolTip() or widget.width() <= 0:
        return
    full_text = widget.text()
    elided = widget.fontMetrics().elidedText(
        full_text,
        Qt.TextElideMode.ElideRight,
        widget.contentsRect().width(),
    )
    if elided != full_text:
        widget.setToolTip(full_text)
```

Add the five integer geometry tokens to `Theme.METRICS`. Implement both stylesheet helpers only with existing semantic `Theme.hex(...)` colors and visible keyboard focus borders.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `uv run pytest tests/test_theme.py tests/test_ui_layout.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/theme.py src/ui/layout_utils.py tests/test_theme.py tests/test_ui_layout.py
git commit -m "feat: add shared UI layout primitives"
```

### Task 2: Make navigation, home, chat, and artifacts responsive and localized

**Files:**

- Modify: `src/ui/navigation_rail.py`
- Modify: `src/ui/home_page.py`
- Modify: `src/ui/chat/chat_panel.py`
- Modify: `src/ui/chat/artifact_sidebar.py`
- Modify: `resources/translations/zh_CN.yaml`
- Modify: `resources/translations/en.yaml`
- Modify: `tests/test_artifact_sidebar.py`
- Modify: `tests/test_ui_layout.py`

**Interfaces:**

- Consumes Task 1 helpers.
- Produces `ArtifactSidebar.refresh_language()` and `ArtifactSidebar.refresh_theme()`; both retain the active session and artifact records.

- [ ] **Step 1: Write failing locale and layout tests**

```python
def test_artifact_sidebar_refreshes_all_static_copy_for_english(qapp):
    sidebar = make_sidebar()
    I18nManager.instance().apply_language("en")
    assert sidebar._title_label.text() == "Artifacts"
    assert sidebar._collapse_button.toolTip() == "Expand artifacts"


def test_chat_controls_expand_for_longest_supported_locale(qapp):
    panel = ChatPanel()
    I18nManager.instance().apply_language("en")
    panel.resize(800, 600)
    assert panel._settings_btn.sizeHint().width() <= panel._settings_btn.width()
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/test_artifact_sidebar.py tests/test_ui_layout.py -q`

Expected: FAIL because artifact labels are hard-coded, no sidebar language refresh exists, and fixed text-button widths remain.

- [ ] **Step 3: Implement primary-workspace presentation**

Replace decorative navigation/chat control emoji with `QStyle.StandardPixmap` icons or existing resource icons. Replace fixed text-button widths with shared fixed heights plus `QSizePolicy.Policy.Minimum` or `Preferred`; retain fixed square sizes only for icon-only controls with localized tooltips. Apply shared card/compact-button helpers to quick actions, artifact cards, chat header controls, and attachments. Keep artifact names and paths wrapping; use `apply_elision_tooltip` for single-line session metadata.

- [ ] **Step 4: Add localized artifact copy**

Add this key set to both translation files, using Simplified Chinese values in `zh_CN.yaml`:

```yaml
artifacts:
  title: "Artifacts"
  empty: "No artifacts for this session"
  expand: "Expand artifacts"
  collapse: "Collapse artifacts"
  open: "Open"
  reveal: "Reveal"
  copy_path: "Copy path"
```

Replace all newly touched static strings in these four widgets with translation keys.

- [ ] **Step 5: Run focused workspace tests**

Run: `uv run pytest tests/test_chat_panel.py tests/test_artifact_sidebar.py tests/test_ui_layout.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ui/navigation_rail.py src/ui/home_page.py src/ui/chat/chat_panel.py src/ui/chat/artifact_sidebar.py resources/translations/zh_CN.yaml resources/translations/en.yaml tests/test_artifact_sidebar.py tests/test_ui_layout.py
git commit -m "feat: unify chat and navigation presentation"
```

### Task 3: Normalize management pages, dialogs, and theme refresh behavior

**Files:**

- Modify: `src/ui/plugins/plugin_panel.py`
- Modify: `src/ui/packages/package_panel.py`
- Modify: `src/ui/settings/settings_panel.py`
- Modify: `src/ui/plugins/permission_dialog.py`
- Modify: `resources/translations/zh_CN.yaml`
- Modify: `resources/translations/en.yaml`
- Modify: `tests/test_ui_layout.py`

**Interfaces:**

- Consumes Tasks 1–2 shared helpers and translation behavior.
- Produces management dialogs that use `setMinimumSize` and layout-managed content instead of fixed whole-dialog dimensions.

- [ ] **Step 1: Write failing management-page geometry tests**

```python
@pytest.mark.parametrize("locale", ["zh_CN", "en"])
def test_install_dialog_uses_layout_driven_size_for_every_locale(qapp, locale):
    I18nManager.instance().apply_language(locale)
    dialog = PluginInstallDialog()
    assert dialog.minimumWidth() >= dialog.sizeHint().width()
    assert dialog.maximumWidth() == QWIDGETSIZE_MAX
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/test_ui_layout.py -q`

Expected: FAIL because install dialogs use fixed dimensions and management action buttons use fixed text widths.

- [ ] **Step 3: Implement layout-managed dialogs and panels**

Use:

```python
dialog.setMinimumSize(460, 0)
dialog.resize(dialog.sizeHint().expandedTo(dialog.minimumSizeHint()))
action_button.setFixedHeight(Theme.METRICS["compact_control_height"])
action_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
```

Apply shared header/card/button styles to plugin, package, settings, and permission widgets. Convert touched hard-coded labels to translation keys, make descriptions wrap, and apply full-text tooltips for bounded metadata labels.

- [ ] **Step 4: Run management and theme tests**

Run: `uv run pytest tests/test_theme.py tests/test_plugin_manager.py tests/test_package_manager.py tests/test_ui_layout.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/plugins/plugin_panel.py src/ui/packages/package_panel.py src/ui/settings/settings_panel.py src/ui/plugins/permission_dialog.py resources/translations/zh_CN.yaml resources/translations/en.yaml tests/test_ui_layout.py
git commit -m "feat: make management UI locale resilient"
```

### Task 4: Verify full UI regression and visual acceptance

**Files:**

- Modify: `tests/test_ui_layout.py`
- Modify: `docs/superpowers/specs/2026-07-18-ui-visual-consistency-i18n-design.md` only if a verified implementation deviation must be documented.

**Interfaces:**

- Consumes the completed widgets from Tasks 1–3.
- Produces automated coverage for dark/light and Chinese/English at 800×600 and 1440×900.

- [ ] **Step 1: Write the final parameterized window check**

```python
@pytest.mark.parametrize("theme", [ThemeType.DARK, ThemeType.LIGHT])
@pytest.mark.parametrize("locale", ["zh_CN", "en"])
def test_main_window_primary_controls_are_not_clipped(qapp, theme, locale):
    Theme.set_theme(theme)
    I18nManager.instance().apply_language(locale)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    assert_no_required_control_is_clipped(window)
```

The helper must check visible `QAbstractButton`, `QLabel`, `QComboBox`, and `QLineEdit` with non-empty static text, skip intentionally wrapping labels and document/message views, and accept a smaller content rectangle only when the widget tooltip equals its full text.

- [ ] **Step 2: Run the new visual regression test**

Run: `uv run pytest tests/test_ui_layout.py -q`

Expected: PASS for both themes and both locales.

- [ ] **Step 3: Run static checks and full regression**

Run: `uv run ruff check src/ui tests/test_theme.py tests/test_artifact_sidebar.py tests/test_ui_layout.py`

Expected: no lint errors.

Run: `uv run pytest -q`

Expected: all tests pass; the SolidWorks live test remains skipped unless `SOLIDWORKS_LIVE_TEST=1` is set.

- [ ] **Step 4: Manually inspect visual states**

Launch the desktop app and inspect Home, AI Assistant, Plugins, Packages, Settings, and Node Editor in Chinese/English and dark/light themes at 800×600 and 1440×900. Confirm no horizontal overflow, clipped required labels, missing focus border, or inconsistent card/button treatment.

- [ ] **Step 5: Commit final verification coverage**

```bash
git add tests/test_ui_layout.py docs/superpowers/specs/2026-07-18-ui-visual-consistency-i18n-design.md
git commit -m "test: cover multilingual UI layout"
```
