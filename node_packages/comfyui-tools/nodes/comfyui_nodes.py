# -*- coding: utf-8 -*-
"""
ComfyUI 图像生成节点定义

提供：
- comfyui.text_to_image: 文生图
- comfyui.image_to_image: 图生图
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

import aiohttp

from src.engine.definitions import NodeDefinition, PortDefinition, PortType
from src.utils.logger import get_logger

_logger = get_logger(__name__)

# 默认配置
_DEFAULT_BASE_URL = "http://localhost:8050"
_DEFAULT_CHECKPOINT = "flux1-dev.safetensors"


def _run_async(coro):
    """在同步环境中运行异步协程"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import threading
        result = [None, None]
        def _target():
            try:
                result[0] = asyncio.run(coro)
            except Exception as e:
                result[1] = e
        t = threading.Thread(target=_target)
        t.start()
        t.join(timeout=310)
        if result[1]:
            raise result[1]
        return result[0]
    else:
        return asyncio.run(coro)


async def _text_to_image_async(
    prompt: str,
    output_name: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = -1,
    cfg_scale: float = 3.5,
    sampler_name: str = "dpmpp_2m",
    scheduler: str = "simple",
    checkpoint: str = _DEFAULT_CHECKPOINT,
    base_url: str = _DEFAULT_BASE_URL,
    workflow_path: str = "",
) -> Dict[str, Any]:
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "scheduler": scheduler,
        "checkpoint": checkpoint,
    }
    if seed is not None and seed >= 0:
        payload["seed"] = seed

    if workflow_path and os.path.exists(workflow_path):
        with open(workflow_path, "r", encoding="utf-8") as f:
            payload["workflow"] = json.load(f)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/api/v1/text-to-image",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=300),
        ) as response:
            if response.status == 200:
                image_data = await response.read()
                output_path = os.path.join("output", "comfyui", output_name)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_data)
                return {"image_path": output_path, "success": True}
            else:
                error = await response.text()
                return {"image_path": "", "success": False, "error": f"HTTP {response.status}: {error}"}


def _execute_text_to_image(
    prompt: str,
    output_name: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = -1,
    cfg_scale: float = 3.5,
    base_url: str = _DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    result = _run_async(
        _text_to_image_async(
            prompt=prompt,
            output_name=output_name,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            seed=seed,
            cfg_scale=cfg_scale,
            base_url=base_url,
        )
    )
    if result.get("success"):
        return {"image_path": result["image_path"], "status": "成功"}
    return {"image_path": "", "status": f"失败: {result.get('error', '未知错误')}"}


comfyui_text_to_image = NodeDefinition(
    node_type="comfyui.text_to_image",
    display_name="文生图",
    description="使用ComfyUI根据文本提示词生成图像",
    category="comfyui",
    icon="🎨",
    inputs=[
        PortDefinition("prompt", PortType.STRING, "正向提示词",
                       widget_type="text_edit"),
        PortDefinition("output_name", PortType.STRING, "输出文件名", default="output.png"),
        PortDefinition("negative_prompt", PortType.STRING, "负向提示词",
                       default="", required=False),
        PortDefinition("width", PortType.INTEGER, "图像宽度", default=1024),
        PortDefinition("height", PortType.INTEGER, "图像高度", default=1024),
        PortDefinition("steps", PortType.INTEGER, "采样步数", default=20),
        PortDefinition("seed", PortType.INTEGER, "随机种子(-1为随机)", default=-1),
        PortDefinition("cfg_scale", PortType.FLOAT, "CFG引导强度", default=3.5),
        PortDefinition("base_url", PortType.STRING, "API地址",
                       default="http://localhost:8050", required=False),
    ],
    outputs=[
        PortDefinition("image_path", PortType.FILE, "生成图像路径"),
        PortDefinition("status", PortType.STRING, "执行状态"),
    ],
    execute=_execute_text_to_image,
)


# ==================== 2. 图生图 ====================


async def _image_to_image_async(
    prompt: str,
    init_image_path: str,
    output_name: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = -1,
    cfg_scale: float = 3.5,
    strength: float = 0.75,
    base_url: str = _DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    if not os.path.exists(init_image_path):
        return {"image_path": "", "success": False, "error": f"输入图像不存在: {init_image_path}"}

    with open(init_image_path, "rb") as f:
        init_image_data = f.read()

    data = aiohttp.FormData()
    data.add_field("prompt", prompt)
    data.add_field("negative_prompt", negative_prompt)
    data.add_field("width", str(width))
    data.add_field("height", str(height))
    data.add_field("steps", str(steps))
    data.add_field("cfg_scale", str(cfg_scale))
    data.add_field("strength", str(strength))
    data.add_field(
        "init_image",
        init_image_data,
        filename=Path(init_image_path).name,
        content_type="image/png",
    )
    if seed >= 0:
        data.add_field("seed", str(seed))

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/api/v1/image-to-image",
            data=data,
            timeout=aiohttp.ClientTimeout(total=300),
        ) as response:
            if response.status == 200:
                image_data = await response.read()
                output_path = os.path.join("output", "comfyui", output_name)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_data)
                return {"image_path": output_path, "success": True}
            else:
                error = await response.text()
                return {"image_path": "", "success": False, "error": f"HTTP {response.status}: {error}"}


def _execute_image_to_image(
    prompt: str,
    init_image_path: str,
    output_name: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = -1,
    cfg_scale: float = 3.5,
    strength: float = 0.75,
    base_url: str = _DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    result = _run_async(
        _image_to_image_async(
            prompt=prompt,
            init_image_path=init_image_path,
            output_name=output_name,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            seed=seed,
            cfg_scale=cfg_scale,
            strength=strength,
            base_url=base_url,
        )
    )
    if result.get("success"):
        return {"image_path": result["image_path"], "status": "成功"}
    return {"image_path": "", "status": f"失败: {result.get('error', '未知错误')}"}


comfyui_image_to_image = NodeDefinition(
    node_type="comfyui.image_to_image",
    display_name="图生图",
    description="使用ComfyUI根据输入图像和提示词生成新图像",
    category="comfyui",
    icon="🖼️",
    inputs=[
        PortDefinition("prompt", PortType.STRING, "正向提示词",
                       widget_type="text_edit"),
        PortDefinition("init_image_path", PortType.FILE, "输入图像路径",
                       widget_type="file_picker"),
        PortDefinition("output_name", PortType.STRING, "输出文件名", default="output.png"),
        PortDefinition("negative_prompt", PortType.STRING, "负向提示词",
                       default="", required=False),
        PortDefinition("strength", PortType.FLOAT, "变换强度(0-1)", default=0.75),
        PortDefinition("width", PortType.INTEGER, "图像宽度", default=1024),
        PortDefinition("height", PortType.INTEGER, "图像高度", default=1024),
        PortDefinition("steps", PortType.INTEGER, "采样步数", default=20),
        PortDefinition("seed", PortType.INTEGER, "随机种子(-1为随机)", default=-1),
        PortDefinition("cfg_scale", PortType.FLOAT, "CFG引导强度", default=3.5),
        PortDefinition("base_url", PortType.STRING, "API地址",
                       default="http://localhost:8050", required=False),
    ],
    outputs=[
        PortDefinition("image_path", PortType.FILE, "生成图像路径"),
        PortDefinition("status", PortType.STRING, "执行状态"),
    ],
    execute=_execute_image_to_image,
)
