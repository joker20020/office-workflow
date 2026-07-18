# SolidWorks 分支 Skill 与主提示词设计

## 目标

将 `solidworks` 分支的主智能体恢复为通用任务代理，并把端到端 AR 装配约束保留在可按需启用的 `ar-assembly-delivery` Skill 中。

## 决策

- 保留 Skill 名称和目录 `skills/ar-assembly-delivery`，避免破坏现有手动注册路径。
- Skill 的三维建模入口固定为公开子智能体 `tool_solidworks_model`；主智能体不直接使用内部 SolidWorks MCP 工具。
- 三维阶段必须交付并交接 `.sldprt`、`.step`、`.stl` 与 preview，以及尺寸、特征树、验证结果和警告；不再提及 Blender 或 `.blend`。
- `config/settings.yaml` 与 `DEFAULT_SYSTEM_PROMPT` 使用完全相同的通用提示词。提示词仅在需要原生 CAD 且该能力可用时优先选择 SolidWorks，不规定所有任务的执行顺序。
- Skill 元数据仅使用 ASCII，防止 Windows 默认编码导致读取乱码。

## 验收

- 主提示词不包含固定四阶段或具体工作流工具名，且含有通用代理、按需选择、SolidWorks 与真实结果约束。
- Skill 明确要求 `tool_solidworks_model` 和四类 SolidWorks 产物，且不包含 Blender。
- 元数据可以以 UTF-8 读取且内容仅含 ASCII。
