# General Agent and AR Delivery Skill Design

## Goal

Make the main AI assistant a general-purpose task agent and move the specialised
end-to-end AR assembly delivery process into an optional project skill.

## Main system prompt

The configured prompt and the hard-coded fallback will describe a general
assistant that interprets user intent, selects relevant tools and enabled
skills, answers directly when no tool is needed, and reports only verified
tool outcomes. It will not prescribe a global tool sequence, mandate planning
for every task, or imply that every request needs process planning, images,
3D modelling, and Unity.

## Optional skill

`skills/ar-assembly-delivery/SKILL.md` will trigger only for requests to
deliver a complete AR-assisted assembly solution spanning process planning,
visual resources, 3D modelling, and Unity AR integration. It contains the
former phase ordering, result-validation, complete-handoff, retry, failure,
and final-report rules. Individual requests for a document, image, model, or
Unity change do not activate it.

The project does not auto-register the skill. A user adds and enables its
directory through the assistant settings when it is required.

## Verification

- Tests assert both the configured and fallback prompts do not contain fixed
  pipeline tool names or mandatory four-stage wording.
- Tests assert the skill frontmatter, trigger description, and core validation
  guidance are present and the project skill directory is discoverable.
