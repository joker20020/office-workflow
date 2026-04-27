# -*- UTF-8 -*-
# @author   : 40599
# @time     : 2026/2/5 10:43
# @version  : V1
import json

import aiohttp
import asyncio
from typing import Optional
import os


class APIRequester:
    def __init__(self,
                 base_url="http://localhost:8000/api/v1",
                 data_dir="../data/",
                 embed_path="/embed",
                 rerank_path="/rerank",
                 image_path="/images",
                 workflow_path="../data/workflow/Flux-Dev-ComfyUI-Workflow.json"):
        self.base_url = base_url
        self.data_dir = data_dir
        self.embed_path = embed_path
        self.rerank_path = rerank_path
        self.image_path = image_path
        with open(workflow_path, encoding="utf-8") as f:
            self.workflow = json.load(f)

    async def query_embedding(self, text: Optional[str], embed_image_path: Optional[str]):
        url = f"{self.base_url}{self.embed_path}"

        assert text or embed_image_path, "text 和 image_path 不能同时为空"

        if embed_image_path:
            with open(embed_image_path, "rb") as f:
                image = f.read()

        data = aiohttp.FormData()
        data.add_field("text", text)
        data.add_field("image", image if embed_image_path else "", filename="embed_image.png",
                       content_type="image/png"
                       if embed_image_path and embed_image_path.split(".")[-1] == "png"
                       else "image/jpeg")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"嵌入向量维度：{result['dimension']}")
                    print(f"嵌入向量：{result['vector']}")
                else:
                    print(f"请求失败，状态码：{response.status}")
        return result

    async def query_rerank(self,
                           query_type: str,
                           query_text: Optional[str],
                           query_image_path: Optional[str],
                           doc_type: str,
                           doc_text: Optional[str],
                           doc_image_path: Optional[str],
                           ):
        url = f"{self.base_url}{self.rerank_path}"
        assert query_type in ["text", "image"], "query_type 必须为 'text' 或 'image'"
        assert doc_type in ["text", "image"], "doc_type 必须为 'text' 或 'image'"
        assert query_text or query_image_path, "query_text 和 query_image_path 不能同时为空"
        assert doc_text or doc_image_path, "doc_text 和 doc_image_path 不能同时为空"
        if query_image_path:
            with open(query_image_path, "rb") as f:
                query_image = f.read()
        if doc_image_path:
            with open(doc_image_path, "rb") as f:
                doc_image = f.read()

        data = aiohttp.FormData()
        data.add_field("query_type", query_type)
        if query_type == 'text':
            data.add_field("query_text", query_text if query_text else "")
        else:
            data.add_field("query_image", query_image if query_image_path else "", filename="query_image.png",
                           content_type="image/png"
                           if query_image_path and query_image_path.split(".")[-1] == "png"
                           else "image/jpeg")
        data.add_field("document_type", doc_type)
        if doc_type == 'text':
            data.add_field("document_text", doc_text if doc_text else "")
        else:
            data.add_field("document_image", doc_image if doc_image_path else "", filename="doc_image.png",
                           content_type="image/png"
                           if doc_image_path and doc_image_path.split(".")[-1] == "png"
                           else "image/jpeg")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"排序结果：{result['score']}")
                else:
                    print(f"请求失败，状态码：{response.status}")

        return result

    async def get_image(self, filename: str):
        url = f"{self.base_url}{self.image_path}/{filename}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    with open(f"{self.data_dir}img/{filename}", "wb") as f:
                        f.write(image_data)
                    return image_data
                else:
                    print(f"请求失败，状态码：{response.status}")

    async def text_to_image(
            self,
            prompt: str,
            output_name: str,
            negative_prompt: str = "",
            width: int = 1024,
            height: int = 1024,
            steps: int = 20,
            seed: int | None = None,
            cfg_scale: float = 3.5,
            sampler_name: str = "dpmpp_2m",
            scheduler: str = "simple",
            checkpoint: str = "flux1-dev.safetensors",
            loras: list[dict] | None = None,
    ) -> bool:
        """
        文生图请求

        Args:
            prompt: 正向提示词
            output_name: 输出图像名称
            negative_prompt: 负向提示词
            width: 图像宽度
            height: 图像高度
            steps: 采样步数
            seed: 随机种子
            cfg_scale: CFG 引导强度
            sampler_name: 采样器名称
            scheduler: 调度器名称
            checkpoint: 模型检查点
            loras: LoRA 列表

        Returns:
            是否成功
        """
        workflow = self.workflow

        # 添加后缀
        name_split = output_name.split(".")
        if name_split[-1] not in ["png", "jpg", "jpeg"]:
            name_split.append(".png")
            output_name = "".join(name_split)

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
            "workflow": workflow,
        }

        if seed is not None:
            payload["seed"] = seed

        if loras:
            payload["loras"] = loras

        print(f"\n[Text-to-Image] 正在生成: {prompt[:50]}...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.base_url}/text-to-image",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        with open(f"{self.data_dir}img/{output_name}", "wb") as f:
                            f.write(image_data)
                        print(f"[Text-to-Image] 成功! 保存至: {output_name}")
                        return True
                    else:
                        error = await response.text()
                        print(f"[Text-to-Image] 失败: {response.status} - {error}")
                        return False
        except asyncio.TimeoutError:
            print("[Text-to-Image] 超时!")
            return False
        except Exception as e:
            print(f"[Text-to-Image] 错误: {e}")
            return False


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    requester = APIRequester(base_url=os.environ["RAG_BASE_URL"])
    # asyncio.run(requester.query_embedding("这是一个测试", "../data/test.png"))
    # asyncio.run(requester.query_rerank("text", "这是一个测试", None, "text", "这是一个测试", None))
    # asyncio.run(requester.get_image("反推堵盖1.png"))
    asyncio.run(requester.text_to_image("生成一张2D平面工程图风格的螺母图片，并配上一个指示顺时针旋转的箭头", "test.png"))
