# Artifact Sidebar Binary Visibility Design

## Goal

Make the assistant artifact sidebar either fully visible or fully hidden, while
preserving user-controlled width adjustment whenever it is visible.

## Interaction

- The chat header's **Artifacts** button is the only visibility toggle.
- Hidden means the sidebar widget is hidden from the splitter; no 36 px compact
  rail or internal collapse button remains.
- Visible means the sidebar is restored at its most recent valid width, or at a
  readable default width on first use.
- The splitter handle remains draggable while visible.  Its width is constrained
  to a readable lower bound and an application-appropriate upper bound, so a
  drag cannot create an effectively hidden third state.

## Theme behavior

- The sidebar root uses its own object-name selector instead of inheriting a
  generic card rule.
- Its scroll viewport, category sections, cards, labels, and action buttons use
  semantic `Theme` colors and are rebuilt on a theme refresh.
- The same hierarchy therefore remains legible in both dark and light themes.

## Verification

- Tests cover the two-state visibility contract, restoration of a valid width,
  removal of the internal toggle, and theme selector/application behavior.
- Existing artifact opening, path validation, and session refresh behavior are
  unchanged.
