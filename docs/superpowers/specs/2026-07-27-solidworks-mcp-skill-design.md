# SolidWorks MCP Completion and Skill Design

## Goal

Make every SolidWorks MCP tool exposed to the modeling subagent executable for
its documented contract, then provide a plugin-private AgentScope Skill that
guides only the SolidWorks subagent through those verified operations.

## Current State

The MCP already supports a basic closed loop: a new part, sketches on the
three standard planes, lines/circles/center rectangles, dimensions, extrude,
revolve, cut-extrude, inspection, and the four required artifacts.

Five published tools currently validate their inputs and then always return an
unsupported-operation result: hole, fillet, chamfer, mirror, and pattern.
Sketching is also limited to standard planes and lacks arc geometry. These
gaps make the published tool schema and the subagent workflow inconsistent.

## MCP Changes

1. Keep existing opaque document, sketch, entity, feature, face, and edge
   references. Never accept raw COM objects, arbitrary macros, or paths.
2. Add a face-based sketch operation that accepts an inspected `face_ref`.
   The service verifies the reference belongs to the requested document before
   delegating to the COM adapter.
3. Extend sketch geometry with a bounded arc variant while preserving the
   existing line, circle, and center-rectangle schemas.
4. Implement the five existing published feature operations in the COM adapter
   and service layer: Hole Wizard/simple hole, constant-radius fillet,
   distance-angle chamfer, plane mirror, and linear/circular feature patterns.
   Each operation must validate typed references and return a new opaque
   `FeatureRef` only after SolidWorks reports success.
5. Inspect after feature creation and use persistent references to refresh
   faces, edges, and features before dependent operations.
6. Preserve the artifact policy: the MCP alone issues paths under `data`, and
   only native part, STEP, STL, and PNG preview outputs may be persisted.

## Skill

Create `plugins/solidworks_agent/skills/solidworks-feature-modeling/` with a
standard `SKILL.md` and Agent metadata. The Skill will:

- require only the dedicated SolidWorks MCP tools;
- select the smallest verified sequence for the requested model;
- require an inspection before using face, edge, or feature references;
- use dimensions and document units explicitly;
- require inspection after every modifying feature;
- always save the native part, export STEP and STL, and capture a preview;
- report only actual MCP results and persisted artifact paths.

`SolidWorksAgentTools` passes this directory through
`Toolkit(skills_or_loaders=[...])`, keeping it private to the SolidWorks
subagent and independent of the application's global Skill manager.

## Error Handling

Reject unsupported geometry, invalid topology references, invalid units, and
unverified COM results before they reach subsequent tool calls. A failed
feature leaves no claimed `FeatureRef`; the subagent must report the failed
operation and continue only when the inspected model supports a safe next
step. stdio remains UTF-8 JSON-RPC only, with application logging directed to
stderr in the child process.

## Verification

- Unit-test every schema, ownership check, and adapter-to-service delegation.
- Extend the FastMCP schema test to cover new operations.
- Extend the opt-in SolidWorks 2023 live test with at least one face-based
  sketch and each newly implemented feature when the required geometry can be
  created deterministically.
- Test that the Skill folder is valid and that the SolidWorks Toolkit receives
  its path automatically.

## Scope

This work does not add assemblies, drawings, arbitrary file access, arbitrary
COM execution, macro execution, or user-selected export paths.
