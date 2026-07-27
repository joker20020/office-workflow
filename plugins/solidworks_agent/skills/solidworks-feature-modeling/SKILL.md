---
name: solidworks-feature-modeling
description: Use when an agent must create, inspect, modify, save, or export a feature-level SolidWorks part through the project-local SolidWorks MCP, including sketches, extrudes, cuts, holes, fillets, chamfers, mirrors, patterns, STEP, STL, or PNG deliverables.
---

# SolidWorks Feature Modeling

Create auditable parametric parts only through the dedicated SolidWorks MCP tools. Keep every operation feature-level, inspect topology after model-changing operations, and report only verified artifacts.

## Workflow

1. Start with `solidworks_status`, then create one part with `solidworks_new_part`. All lengths use the part unit.
2. Build sketches with lines, circles, centre rectangles, or three-point arcs. Close each sketch before an extrude, cut, or revolve.
3. After every model-changing feature, use `solidworks_inspect_model`; pass only returned owned face, edge, and feature references to later tools.
4. Use `solidworks_create_sketch_on_face` and `solidworks_hole` only with an inspected owned planar face. Hole positions are face-local coordinates.
5. Apply fillets/chamfers to inspected edge references. Mirror and pattern inspected feature references across standard planes only.
6. Finish with `solidworks_save_model`, `solidworks_export_step`, `solidworks_export_stl`, and `solidworks_capture_preview`.

## Safe Tool Contracts

| Need | Use |
| --- | --- |
| Base volume | Closed sketch + `solidworks_extrude` or `solidworks_revolve` |
| Material removal | Closed sketch + `solidworks_cut_extrude` |
| Standard hole | `solidworks_hole` with `simple`, `counterbore`, or `countersink` |
| Edge finish | `solidworks_fillet` or `solidworks_chamfer` |
| Repetition | `solidworks_mirror_feature` or `solidworks_pattern_feature` |
| Delivery | Native save plus STEP, STL, and isometric PNG |

Never use shell commands, macros, arbitrary COM access, or arbitrary output paths. Do not reuse topology references after a model change; inspect again.

## Result Contract

Return the required execution-result Markdown. For successful work, list exactly the verified native part, STEP, STL, and PNG paths under `data`; state inspected topology and dimensions in Concrete Result and Verification. If a tool fails, stop, report its message, and do not claim a generated artifact.
