# Session History Header Responsive Design

## Goal

Keep the session-history title and the new-session action fully readable while
the assistant's session rail is resized.

## Interaction

- At a width that can fit both controls, the title and the New Session button
  remain on one horizontal row.
- Below that breakpoint, the header changes to two rows: the title occupies the
  first row and the button is right-aligned on the second.
- Resizing back across the breakpoint restores the compact single-row layout.
- The session rail remains draggable and its existing session behavior is
  unchanged.

## Accessibility and localization

- The title and button retain their full translated text in both layouts.
- The title is never made readable only through an elision tooltip.
- The header's height and all margins are recalculated with the current theme
  and do not change color semantics.

## Verification

- A UI test resizes the session rail under Chinese and English translations and
  asserts the title has enough width or is on its own row.
- The test also confirms the layout switches back to the horizontal row at a
  normal rail width.
