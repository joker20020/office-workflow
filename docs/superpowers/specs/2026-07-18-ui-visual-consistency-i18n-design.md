# UI visual consistency and multilingual layout design

## Goal

Refine the existing desktop UI without changing its information architecture. Keep the current dark graphite and indigo identity, make component styling consistent across pages, and ensure both Chinese and English strings remain readable at supported window sizes.

## Scope

- Preserve the application navigation, page structure, feature behavior, and light/dark theme switch.
- Establish a small shared UI token layer for spacing, control heights, radii, and semantic states in addition to the existing theme colors.
- Apply the shared styles to the main window, navigation rail, home page, chat workspace, artifact sidebar, plugin/package pages, settings, dialogs, and node-editor chrome.
- Replace decorative emoji used as interface controls with a consistent Qt icon treatment. Message content and user-supplied text are out of scope.
- Replace hard-coded UI labels with translation keys where an equivalent interface string is required.
- Remove width and height constraints that can truncate translated labels. Use layout stretch, sensible minimum sizes, wrapping for descriptive text, and elision plus tooltip only for bounded list rows where preserving layout is necessary.
- Ensure theme and language refreshes restyle dynamic widgets without changing application state.

## Visual system

- **Surface hierarchy:** primary canvas, elevated panels, cards, and selected/hover states use the existing graphite scale in dark mode and its corresponding light-mode scale.
- **Accent:** indigo remains the sole primary action and focus color. Success, warning, and error retain their semantic colors and are never the only status indicator.
- **Density:** controls use shared compact heights; page headers, cards, and content columns share consistent spacing and corner radii.
- **Typography:** use the platform UI font with a CJK-capable fallback. Labels favor natural size hints over fixed widths. Headings, secondary metadata, and paths have explicit visual hierarchy.
- **Interaction:** buttons and actionable cards have stable hover, pressed, disabled, focus, and tooltip states. Motion remains minimal and respects the existing animation behavior.

## Multilingual behavior

- English and Simplified Chinese are the acceptance locales.
- Buttons, toolbar actions, tab labels, navigation rows, dialogs, and configuration forms must use their content size or flexible layouts rather than fixed label widths.
- Long descriptions and file paths may wrap; compact list labels may elide only when a tooltip exposes the full localized string or path.
- Changing language refreshes visible static labels and dynamic session/artifact controls without recreating or losing data.
- Missing translation keys remain observable through the existing i18n fallback behavior and are covered by tests.

## Implementation boundaries

- Add reusable helpers/tokens in the UI theme layer rather than introducing a new UI framework.
- Keep domain behavior in existing panels; changes are limited to presentation, localization, and layout behavior.
- Do not alter artifact persistence, agent execution, SolidWorks/Blender integration, workflow execution, or session deletion behavior.

## Verification

- Add focused tests for translation completeness where labels are newly keyed.
- Add Qt layout tests at the current minimum window size and representative desktop sizes for Chinese and English. Tests assert no required control has clipped text; bounded rows must provide a tooltip when elided.
- Run UI-related tests and the full test suite after implementation.
- Manually inspect the main pages in both themes and both languages for contrast, alignment, focus visibility, and horizontal overflow.

## Non-goals

- No redesign of the navigation hierarchy or workflow/node canvas interactions.
- No new locale beyond Chinese and English in this change.
- No changes to user content formatting, generated artifacts, or application data schema.
