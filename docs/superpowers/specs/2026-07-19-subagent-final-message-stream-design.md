# Subagent Final Message Stream Design

## Problem

`Agent.reply_stream()` intentionally drops every final `Msg`. The plugin's
subagent bridge currently consumes that public stream and rebuilds final text
only from block-delta events. A Blender or Unity subagent can therefore finish
with an empty bridge reply when its final answer is delivered as an
`AssistantMsg` rather than as text deltas.

## Design

The bridge will prefer AgentScope's `_reply()` event generator. Unlike
`reply_stream()`, it retains both ordinary events and the terminal `Msg`.
The bridge continues publishing its existing display-safe progress events, and
uses the final message as the returned result when one is supplied. For an
agent without `_reply()`, it preserves the existing public-stream fallback.

The trace records whether a terminal message and `ReplyEndEvent` were observed.
If neither final text nor a terminal message is available, the Blender wrapper
returns an explicit abnormal-stream failure containing the last tool and the
missing terminal information. No MCP operation is retried.

## Verification

Tests cover an `_reply()` stream containing tool events plus a final
`AssistantMsg` with no text deltas, and an abnormal stream that ends without a
message or `ReplyEndEvent`. Existing public-stream fake agents remain covered
through the compatibility fallback.
