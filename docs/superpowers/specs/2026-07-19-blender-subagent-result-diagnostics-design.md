# Blender Subagent Result Diagnostics Design

## Scope

This repair applies to `main` only. It improves the Blender subagent stream
transport and the failure report produced when an MCP tool call does not yield a
tool result or a final assistant handoff. It does not relax the required final
Markdown handoff and does not automatically retry Blender actions.

## Problem

The current progress bridge sends every `ToolCallDeltaEvent` as an internal
marker. A model-generated JSON argument is therefore displayed as many tiny
fragments if the marker leaks through a stream path. More importantly, the
bridge does not retain `ToolCallEndEvent`, `ToolResultEndEvent`, or the reply
finish reason. When the stream ends before a tool result/final text is received,
the Blender wrapper reports only "Blender Agent did not return content".

## Design

1. Capture an execution trace while consuming the subagent event stream:
   reply finish reason, active/last tool identity, finalized arguments, and the
   terminal tool-result state/text.
2. Continue to stream meaningful progress, but publish human-readable summary
   events only. Tool arguments and results may still be assembled incrementally
   internally; the UI receives readable phases such as "Reading Blender scene
   information" and streamed result prose, never JSON argument fragments or
   protocol markers.
3. On an empty final reply, build a structured failure from the captured trace.
   It identifies the last MCP tool and whether it failed, ended without a
   result, or the reply terminated unexpectedly.
4. Keep a UI-side protocol decoder fallback for markers received through a
   normal text delta, so internal transport data cannot appear in chat text.
5. Log one concise diagnostic summary per subagent completion/failure at debug
   level, instead of token-level log entries.

## Safety and Compatibility

The existing final-handoff validation still verifies successful replies. The
repair intentionally does not retry a missing Blender MCP operation: automatic
replay could duplicate model changes or file exports. Existing callers retain
their return type; execution trace collection is optional.

## Verification

Tests will cover an incomplete tool call that has no tool result, a failed tool
result with no final text, human-readable streamed activity without raw JSON,
and UI suppression of a private marker received on the fallback text path.
