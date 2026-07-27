# SolidWorks MCP tool contracts design

## Goal

Make the project-local SolidWorks MCP self-describing enough for a model to choose tools, construct valid arguments, retain safe topology references, and understand the required feature workflow without relying on the subagent prompt alone.

## Design

Each public FastMCP tool receives a concise, imperative docstring containing:

- its purpose and valid workflow position;
- required owned identifiers and how they are obtained;
- enum constraints, units, or exact object shapes where relevant;
- the result type or appropriate next step;
- artifact/path rules for save and export operations.

The wording groups tools into four model-visible stages:

1. Session and part creation.
2. Sketch construction and feature creation.
3. Topology inspection and feature editing.
4. Persisting and exporting artifacts.

## Safety and reference semantics

Descriptions state that document, face, edge, and feature identifiers are server-owned references. Any topology-changing operation requires a subsequent `solidworks_inspect_model` call before using faces, edges, or features again. Tools accept no caller-provided file paths, macros, or raw COM data.

## Parameter guidance

Complex argument descriptions include compact JSON-shaped examples for sketch geometry, dimensions, holes, chamfers, and patterns. Every dimensional input is explicitly stated to use the unit supplied to `solidworks_new_part`; all feature angles use degrees.

## Testing

Add a schema-facing test that extracts all public FastMCP tool descriptions and asserts each is non-empty. Assert the workflow-critical descriptions mention owned/inspected references, unit or angle semantics, and post-mutation inspection where applicable. Keep service behavior and tool signatures unchanged.

## Non-goals

Do not add new MCP tools, allow arbitrary filesystem paths, expose COM APIs, or replace the plugin-level SolidWorks modeling Skill.
