# Artifact Tracking, Data Paths, and SolidWorks MCP Design

## Status and delivery order

This design extends the completed AgentScope 2.0.4 migration. Artifact tracking, event presentation, and output-path work are implemented on the current branch. SolidWorks MCP implementation and default-modeling workflow changes are deferred to the `solidworks_version` branch so they do not affect the current branch.

Implementation order is binding:

1. Current branch: persistent artifact registry, right sidebar, and AgentScope event presentation.
2. Current branch: unified, session-scoped output-path policy and migration of existing generators, including Blender.
3. `solidworks_version` branch: a project-local SolidWorks 2023 MCP, then replacement of the default modeling workflow.

## Goals

- Show every verified text, image, model, and export artifact produced or modified by the main agent or a subagent.
- Persist artifact metadata across application restarts and associate it with the existing chat-history session.
- Keep final subagent output as the parent agent's tool result while streaming the subagent's execution events inside that same tool-call card.
- Constrain user-visible output to categorized, session-scoped directories below project-root `data`.
- Use a self-owned local SolidWorks 2023 MCP for default 3D modeling, with native and exchange exports.

## Non-goals

- The artifact sidebar does not create, search, or switch chat sessions; existing left-side session management remains authoritative.
- Deleting a chat session removes only its artifact registry records, never its files on disk.
- RAG/download caches are not user artifacts and are not shown in the sidebar.
- The initial SolidWorks MCP does not expose arbitrary COM execution, arbitrary macros, or unbounded filesystem access.

## 1. Persistent artifact registry and execution events

### Data model

Add an artifact repository/table owned by the existing application database. Every row contains:

- a stable artifact ID and existing chat-session ID;
- producing agent/subagent name and the parent tool-call/event ID where available;
- artifact category, display name, absolute path, `data`-relative path, and creation timestamp;
- integrity/availability state, optional content summary, and optional preview metadata.

Artifacts are registered only after the writing/exporting tool verifies that the resolved path exists and is within the project `data` root. A missing file remains an auditable registry record with an unavailable state. Session deletion cascades to registry rows only; it never deletes session directories or files.

### Event presentation

The parent chat message keeps one tool-call/result card for a subagent invocation. During execution, that card receives a chronological stream of safe AgentScope 2 events: phase boundaries, displayable progress text, nested tool calls/results, artifact confirmations, warnings, failures, and completion. The final structured Markdown handoff stays in the card as the authoritative tool result.

Internal chain-of-thought is never rendered. Only displayable agent text and auditable tool/event payloads are shown. Every confirmed artifact event is immediately registered and updates the sidebar.

## 2. Chat UI and artifact sidebar

The AI assistant receives a right-side artifact panel controlled by an upper-right action. It is collapsed by default so chat remains wide; expanding it reveals artifacts for the currently selected existing chat session.

The panel groups records into documents, images, models, and exports. Each item shows display name, producing agent, timestamp, verification/availability state, and full absolute path. It offers system-default open, copy absolute path, and reveal-in-file-manager actions. All actions revalidate the `data` boundary and availability before use.

The sidebar contains no history selector or search. When left-side session management switches the active session, the panel reloads that session's records. Artifact IDs connect chat-card file links and sidebar entries so each can locate the other.

## 3. Output-path policy

Introduce one project-root-aware path service and require file-producing tools to use it. The service normalizes filenames, creates directories, resolves real paths, rejects traversal and symlink escapes, and verifies output existence before artifact registration.

| Purpose | Required destination |
|---|---|
| Documents, process JSON, reports, Markdown | `data/documents/<session-id>/` |
| Generated/renders/preview images | `data/images/<session-id>/` |
| Native Blender/SolidWorks models | `data/models/<session-id>/` |
| STEP, STL, PDF and other delivery exports | `data/exports/<session-id>/` |
| RAG/download/intermediate cache | `data/tmp/` |

Existing Blender behavior is migrated to this service: `.blend` and native assets go to `models`, rendered images/textures/previews to `images`, and externally consumable exports to `exports`. A tool returning an out-of-bound path is not a successful artifact result; the parent receives a path-policy failure.

RAG cache files are intentionally excluded from artifact registration and may be overwritten on refresh.

## 4. SolidWorks 2023 MCP (implemented last)

Create a self-contained `plugins/solidworks_agent` plugin. Its public plugin tool follows the existing Blender pattern: the main agent calls one SolidWorks subagent tool, that subagent owns a stateful stdio MCP client, and its final structured Markdown is returned as the parent tool result. The plugin contains its own Python stdio MCP server and local SolidWorks 2023 COM adapter; no SolidWorks MCP implementation is added to `src`. The adapter first attempts to attach to an already running instance and otherwise starts SolidWorks and waits for COM readiness. It records whether it started the instance; disconnecting the MCP never closes a user-owned running instance. Plugin configuration controls cleanup of instances it started.

The MCP has a constrained feature-level API rather than a monolithic free-form part creator.

### Document and sketch tools

- `solidworks_status`
- `solidworks_new_part(session_id, name, unit)`
- `solidworks_create_sketch(document_id, plane)`
- `solidworks_add_sketch_geometry(sketch_id, geometry)`
- `solidworks_add_dimensions(sketch_id, dimensions)`
- `solidworks_close_sketch(sketch_id)`

### Feature tools

- `solidworks_extrude(document_id, sketch_id, depth, direction)`
- `solidworks_revolve(document_id, sketch_id, axis, angle)`
- `solidworks_cut_extrude(document_id, sketch_id, depth)`
- `solidworks_hole(document_id, face_ref, specification, position)`
- `solidworks_fillet(document_id, edge_refs, radius)`
- `solidworks_chamfer(document_id, edge_refs, specification)`
- `solidworks_mirror_feature(document_id, feature_refs, plane)`
- `solidworks_pattern_feature(document_id, feature_ref, pattern)`

### Inspection and delivery tools

- `solidworks_inspect_model(document_id)`
- `solidworks_save_model(document_id)`
- `solidworks_export_step(document_id)`
- `solidworks_export_stl(document_id, mesh_options)`
- `solidworks_capture_preview(document_id, view)`

Each modeling call returns structured Markdown with status, IDs, affected entities, verified absolute paths, validation details, and warnings. The parent agent must use a verified progression: sketch, one feature, inspection, next feature, then save/export. It must not invent feature, face, or edge references.

Native `.sldprt`/`.sldasm` files save to `data/models/<session-id>/`; `.step` and `.stl` exports save to `data/exports/<session-id>/`; previews save to `data/images/<session-id>/`. Confirmed files use the common artifact registry.

On `main`, keep the existing Blender tool and current Blender modeling stage while applying the shared path policy and artifact registry. After the SolidWorks plugin integration tests pass on `solidworks_version`, remove Blender-specific plugin tools, prompts, configuration, and dedicated tests from that branch. The main agent never calls SolidWorks MCP tools directly; it calls the SolidWorks plugin subagent tool.

### First-use operator preparation

Before the first real MCP connection, the operator starts SolidWorks 2023 once, completes its license sign-in, and accepts any Windows COM or firewall prompt for the local application. Later calls may start and attach automatically. No SolidWorks add-in installation is required for the first project-local COM/stdio implementation.

## Error handling and security

- A path violation, unavailable file, export failure, or COM error is an explicit failed tool result and cannot be silently presented as a generated artifact.
- Artifact open/reveal operations use only registered, currently existing files that resolve inside `data`.
- SolidWorks tools accept structured specifications only and do not provide unrestricted macro/script execution.
- SolidWorks connection, file save, and export timeouts surface actionable failures in the tool card and final structured result.

## Verification strategy

- Repository and UI tests cover registry persistence, session-delete record cleanup without disk deletion, path rejection, category routing, and safe open/reveal eligibility.
- Streaming tests cover parent tool-card event ordering, nested subagent events, final Markdown preservation, and immediate artifact registration.
- Existing generator tests cover Blender and RAG cache destination changes.
- SolidWorks MCP unit tests mock the COM adapter; optional Windows integration tests verify attach/start, native save, STEP/STL export, preview capture, and all paths within `data`.
- Full regression runs remain required before the branch is ready for merge.

## Design review checklist

- No placeholder or TBD requirements remain.
- The sidebar/session ownership, session deletion, user artifact/cache separation, and output roots are explicit and non-conflicting.
- SolidWorks remains last in the stated delivery order and does not depend on community MCP packages.
- File-system authority is centralized and applies equally to Blender and SolidWorks.
