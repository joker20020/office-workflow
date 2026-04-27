import asyncio
import os
import json
import base64
from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit, ToolResponse
from agentscope.mcp import HttpStatefulClient, StdIOStatefulClient
from agentscope.formatter import OpenAIChatFormatter, OpenAIMultiAgentFormatter, DeepSeekChatFormatter
from agentscope.message import Msg, TextBlock, ImageBlock, Base64Source
from agentscope.memory import InMemoryMemory
from agentscope.plan import PlanNotebook, Plan
from agentscope.tool import write_text_file, view_text_file
from pydantic.networks import AnyUrl
from dotenv import load_dotenv
from typing import List, Dict
from database import MoyuClient
from util import (
    get_json,
    APIRequester
)

load_dotenv()

requester = APIRequester(
    base_url=os.environ["RAG_BASE_URL"],
    data_dir="./data/",
    workflow_path="./data/workflow/Flux-Dev-ComfyUI-Workflow.json"
)

llm_name = "deepseek-reasoner"# "qwen3.5-plus"
vlm_name = "qwen3-vl-235b-a22b-thinking"


async def unity_agent_tool(task: str, info: Dict[str, List[str]]):
    """根据提供的工序和工步json字符串生成unityAR辅助装配程序

    Args:
        task (str): 对 unity 程序的需求，需要提供包含工序工步的详细描述
        info (Dict[str, List[str]]: 工序工步信息，键为工序名，值为工步名称列表

    """
    # 准备工具
    toolkit = Toolkit()
    unity_mcp = HttpStatefulClient(
        name="unity_mcp",
        transport="streamable_http",
        url="http://localhost:8080/mcp"
    )

    # unity_mcp = StdIOStatefulClient(name="unity_mcp",
    #                                 command="D:\\anaconda\\Scripts\\uvx.exe",
    #                                 args=[
    #                                     "--from",
    #                                     "git+https://github.com/CoplayDev/unity-mcp@v8.3.0#subdirectory=Server",
    #                                     "mcp-for-unity",
    #                                     "--transport",
    #                                     "stdio"
    #                                 ],)

    await unity_mcp.connect()
    # print(await unity_mcp.session.list_resources())
    # print(await unity_mcp.session.list_tools())
    print(os.environ["LLM_API_KEY"])

    # 激活当前unity editor instance
    instances_response = await unity_mcp.session.read_resource(AnyUrl("mcpforunity://instances"))
    instance_hash = json.loads(instances_response.contents[0].text)["instances"][0]["hash"]
    print("instance hash is", instance_hash)
    print(await unity_mcp.session.call_tool("set_active_instance", {"instance": instance_hash}))
    custom_tools_response = await unity_mcp.session.read_resource(AnyUrl("mcpforunity://custom-tools"))
    custom_tools = json.loads(custom_tools_response.contents[0].text)["data"]["tools"]

    useful_tools = ["addXRRig", "addXRSimulator", "addMainCanvas", "addProcess"]
    custom_tools = [tool for tool in custom_tools if tool["name"] in useful_tools]
    print("custom tools:", custom_tools)

    # toolkit.register_tool_function(execute_python_code)
    await toolkit.register_mcp_client(unity_mcp)
    # for tool in toolkit.get_json_schemas():
    #     print(tool)

    unity_agent = ReActAgent(
        name="unity_agent",
        sys_prompt=f"""
        你是顶尖的一个Unity AR程序开发助手,你的任务是使用工具直接帮助用户完成AR程序的开发，你可以使用的custom tools 包括{custom_tools},
        当你使用custom tools中的工具时，不要直接使用，必须通过调用execute_custom_tool工具来使用，execute_custom_tool工具的使用格式如下：
        {{
            "type": "tool_use",
            "name": "execute_custom_tool",
            "input": {{
                "tool_name": "自定义工具名",
                "parameters": {{ 自定义工具参数字典，注意需要传入字典，而不是字符串 }}
            }}
        }}
        一个常用的AR应用初始化流程如下，请直接使用工具一步一步执行并检查每一步的执行结果：
        1.检查场景中是否有XR Rig对象，若不存在则使用自定义工具向场景中添加一个XR Rig对象
        2.检查场景中是否有XR Simulator对象，若不存在则添加一个XR Simulator对象使用户可以在编辑器中模拟XR操作
        3.检查场景中是否有MainCanvas，若不存在则添加一个主界面
        4.根据工序工步信息向主界面中添加工序组
        5.在unity中运行AR程序
        """,
        model=OpenAIChatModel(
            model_name=llm_name,
            api_key=os.environ["LLM_API_KEY"],
            stream=True,
            enable_thinking=False,
            client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
            generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
        ),
        formatter=DeepSeekChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    msg = Msg(
        name="user",
        content=f"请完成以下任务：{task}，可用的工艺信息为：{info}",
        role="user",
    )

    msg_res = await unity_agent(msg)
    await unity_mcp.close()

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )

    # return unity_agent


async def blender_agent_tool(task: str):
    """根据需求完成blender建模

    Args:
        task (str):对 blender 模型的需求
    """
    # 准备工具
    toolkit = Toolkit()
    # blender_mcp = HttpStatefulClient(
    #     name="blender_mcp",
    #     transport="streamable_http",
    #     url="http://localhost:8080/mcp"
    # )

    blender_mcp = StdIOStatefulClient(
        name="blender_mcp",
        command="D:\\anaconda\\Scripts\\uvx.exe",
        args=[
            "blender-mcp"
        ], )

    await blender_mcp.connect()
    print(await blender_mcp.session.list_resources())
    print(await blender_mcp.session.list_tools())

    # custom_tools_response = await blender_mcp.session.read_resource(AnyUrl("unity://custom-tools"))
    # custom_tools = json.loads(custom_tools_response.contents[0].text)["data"]["tools"]
    #
    # useful_tools = ["addXRRig", "addXRSimulator", "addMainCanvas", "addProcess"]
    # custom_tools = [tool for tool in custom_tools if tool["name"] in useful_tools]
    # print("custom tools:", custom_tools)

    await toolkit.register_mcp_client(blender_mcp)
    # for tool in toolkit.get_json_schemas():
    #     print(tool)

    blender_agent = ReActAgent(
        name="blender_agent",
        sys_prompt=f"""你是一个blender建模助手,你的任务是帮助用户在blender应用中完成三维建模
        """,
        model=OpenAIChatModel(
            model_name=llm_name,
            api_key=os.environ["LLM_API_KEY"],
            stream=True,
            enable_thinking=False,
            client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
            generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
        ),
        formatter=DeepSeekChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    msg = Msg(
        name="user",
        content=task,
        role="user",
    )

    msg_res = await blender_agent(msg)
    await blender_mcp.close()

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )


def plan_change_hook(self: PlanNotebook, plan: Plan):
    """

    :param self: PlanNotebook 实例
    :param plan: 当前计划
    :return:
    """
    print(f"{plan.name} - {plan.description}")
    print(f"{self.get_current_hint()}")


async def process_agent_tool(task: str, image_path: str = None, collection_name: str = "process", limit: int = 5):
    """
    根据任务要求，查询向量数据库，生成对应的工序工步内容
    :param task: 任务要求
    :param image_path: 参考图像路径
    :param collection_name: 查询向量数据库名称
    :param limit: 查询向量条数
    :return:
    """
    client = MoyuClient(requester, os.environ["MILVUS_BASE_URL"])
    texts = [task]

    # query database
    query_vector = await client.get_fused_embeddings(text=task, image_path=image_path)
    query_res = client.search(
        data=[query_vector],
        collection_name=collection_name,
        limit=limit,
        output_fields=["text", "subject", "path", "type"],
    )

    # rerank
    rerank_num = limit
    for i in range(len(query_res[0])):
        entity = query_res[0][i]['entity']
        if entity['type'] == "text":
            res = await requester.query_rerank(query_type="text", query_text=texts[-1], query_image_path=None,
                                            doc_type="text", doc_text=entity['text'], doc_image_path=None)
            query_res[0][i]['score'] = res["score"]
        elif entity['type'] == "image":
            res = await requester.query_rerank(query_type="text", query_text=texts[-1], query_image_path=None,
                                            doc_type="image", doc_text=None, doc_image_path=f"./data/img/{entity['path']}")
            query_res[0][i]['score'] = res["score"]

    query_res[0].sort(key=lambda x: x['score'], reverse=True)

    # generate message
    query_content_list = []

    for i in range(rerank_num):
        entity = query_res[0][i]['entity']
        if entity['type'] == "text":
            query_content_list.append(
                TextBlock(type="text", text=f"{i + 1}.{entity['text']}(来源为{entity['path']})\n")
            )
        elif entity['type'] == "image":
            if not os.path.exists(f"./data/img/{entity['path']}"):
                image_data = await requester.get_image(entity['path'])
            else:
                image_data = open(f"./data/img/{entity['path']}", "rb").read()
            query_content_list.append(
                TextBlock(type="text", text=f"{i + 1}.{entity['text']}(来源为{entity['path']})\n")
            )
            query_content_list.append(
                ImageBlock(type="image", source=Base64Source(type="base64",
                                                             media_type="image/png"
                                                             if entity['path'] and entity['path'].split(".")[
                                                                 -1] == "png"
                                                             else "image/jpeg",
                                                             data=base64.b64encode(image_data).decode("utf-8")))
            )
            query_content_list.append(
                TextBlock(
                    type="text",
                    text=f"{i + 1}.{entity['text']}(来源为{entity['path']})\n"
                )
            )

    msg = Msg(
        name="user",
        role="user",
        content=[TextBlock(type="text", text="知识库中搜索有如下结果\n")
                 ] +
                query_content_list +
                [
                    TextBlock(type="text",
                              text=f"用户的问题是:{texts[-1]}, 请你根据知识库结果回答用户的问题，在你回答用户问题时，需要过滤掉搜索中无关的项"),
                    TextBlock(type="text", text="对于装配工序请使用以下json格式模板进行回答：\n"),
                    TextBlock(type="text", text="""
                           {
                                "info":{
                                    "processID":"工序号",
                                    "processName":"工序名称",
                                    "processCharacteristic":"工序特征",
                                    "processType":"工序类型枚举:assemble/measure/postprocess",
                                    "note":"工序备注"
                                },
                                "steps":{
                                    "工步名称":"工步文件路径.json"
                                },
                                "processResources":[
                                    {
                                        "resourceName":"工艺资源名称",
                                        "resourceID":"工艺资源号",
                                        "specification":"工艺资源规格",
                                        "resourceType":"工艺资源类型枚举:tool/people",
                                        "model":"工艺资源模型路径.step"
                                    }    
                                ],
                                "parts":[
                                    {
                                        "partID":"装配件代号",
                                        "partName":"装配件名称",
                                        "partNum":1,
                                        "action":"装配动作",
                                        "model":"装配件模型路径.step"
                                    }
                                ]
                            }
                           """),
                    TextBlock(type="text", text="对于装配工步请使用以下json格式模板进行回答：\n"),
                    TextBlock(type="text", text="""
                           {
                                "info":{
                                    "stepID":"工步号",
                                    "stepName":"工步名称"
                                },
                                "stepContent":[
                                    {
                                        "title":"工步基本内容标题",
                                        "detail":"工步基本内容细节1"
                                    },
                                    {
                                        "title":"测量工步内容标题",
                                        "detail": "测量工步内容细节",
                                        "target":"测量指标",
                                        "inspection_method":"检验方式",
                                        "measure_method":"测量方法",
                                        "times":1,
                                        "resource_name":"资源名称",
                                        "resource_id":"资源代号",
                                        "resource_specification":"资源规格",
                                        "digital":false
                                    }
                                ],
                                "annex":"工步附件路径.*",
                                "animation":"工步装配动画"
                            }
                           """),
                ],
    )

    toolkit = Toolkit()
    toolkit.register_tool_function(write_text_file)
    toolkit.register_tool_function(view_text_file)

    plan_notebook = PlanNotebook()

    process_agent = ReActAgent(
        name="process_agent",
        sys_prompt=f"""
        你是一个工艺规划师,你的任务是根据查询到的知识帮助用户进行工艺规划
        在你进行规划前，请先制定一个工艺规划计划，并使用plan工具创建一个工艺编写任务列表,
        创建的任务列表中，每个任务项代表一个需要完成的任务
        你的工作流程如下：
        1、使用工具将当前任务项标记为进行中
        2、完成该任务项内容所要求的任务
        3、使用工具将已完成的任务项标记为已完成
        4、使用工具检查是否已完成计划列表，若为完成则回到步骤1继续完成，直至计划完成才能结束规划
        每当你完成一个工序或工步文件编写后请按照json模板输出将其完整写入当前文件夹下的文件内进行保存，注意输出文件结构的可读性，同时请确保所有工序工步均保存
        """,
        model=OpenAIChatModel(
            model_name=vlm_name,
            api_key=os.environ["VLM_API_KEY"],
            stream=True,
            enable_thinking=False,
            client_kwargs={"base_url": os.environ["VLM_BASE_URL"]},
            generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
        ),
        formatter=OpenAIMultiAgentFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
        plan_notebook=plan_notebook
    )

    msg_res = await process_agent(msg)
    content = msg_res.get_content_blocks("text")
    if not content:
        content = process_agent.memory.content
    return ToolResponse(
        content=[TextBlock(type="text", text=each["text"])
                 for each in content]
    )


async def comfyui_agent_tool(task: str):
    """根据需求生成图片资源

    Args:
        task (str):对图片资源的需求描述
    """

    async def generate_image_from_text(prompt: str, output_name: str,):
        """
        调用API生成所需的图片

        :param prompt:生成图片的正向提示词
        :param output_name:生成图片的保存名称
        :return:
        """

        success = await requester.text_to_image(prompt, output_name)
        return ToolResponse(content=[
            TextBlock(type="text", text=f"图片生成{'成功' if success else '失败'}")
        ])

    # 准备工具
    toolkit = Toolkit()
    toolkit.register_tool_function(generate_image_from_text)

    comfyui_agent = ReActAgent(
        name="comfyui_agent",
        sys_prompt=f"""
        你是一个ai图片生成助手,你的任务是根据用户的描述，合理细化生成图片细节要求，并调用api进行生成
        注意：请将用户描述往符合图像生成模型要求的方向进行细化，使其包含必要的细节，及要求
        图像应该为2维工程图风格，以指示为主，尽量不要出现人物等元素
        """,
        model=OpenAIChatModel(
            model_name=llm_name,
            api_key=os.environ["LLM_API_KEY"],
            stream=True,
            enable_thinking=False,
            client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
            generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
        ),
        formatter=DeepSeekChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    msg = Msg(
        name="user",
        content=task,
        role="user",
    )

    msg_res = await comfyui_agent(msg)

    return ToolResponse(
        content=msg_res.get_content_blocks("text"),
    )


async def create_router() -> ReActAgent:

    toolkit = Toolkit()
    toolkit.register_tool_function(blender_agent_tool)
    toolkit.register_tool_function(unity_agent_tool)
    toolkit.register_tool_function(process_agent_tool)
    toolkit.register_tool_function(comfyui_agent_tool)

    router = ReActAgent(
        name="router",
        sys_prompt=f"""
        你是一个计划智能体，你的任务是将用户的任务进行规划,并使用不同的工具完成。
        注意:
        在所有任务中工艺生成的优先级是最高的，其他任务都需要依托生成的工艺进行
        在所有任务中生成AR辅助装配程序优先级是最低的，该任务可以利用其他任务的执行结果
        """,
        model=OpenAIChatModel(
            model_name=llm_name,
            api_key=os.environ["LLM_API_KEY"],
            stream=True,
            enable_thinking=False,
            client_kwargs={"base_url": os.environ["LLM_BASE_URL"]},
            generate_kwargs={"max_tokens": 4096, "max_completion_tokens": 4096},
        ),
        formatter=DeepSeekChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=toolkit,
    )

    return router


async def multi_agent_task(message: Msg):

    router = await create_router()
    router_msg = await router(message)


if __name__ == '__main__':
    with open("data/test/process1.json", encoding="utf-8") as f:
        process_info = json.load(f)
        print(process_info)

    with open("data/test/step1.json", encoding="utf-8") as f:
        step_info = json.load(f)
        print(step_info)

    msg = Msg(
        name="user",
        content=f"你好！请参考<./data/img/反推堵盖1.png>图像为我创建一份反推堵盖的安装工艺文件,"
                f"完成后根据该文件帮我在unity里创建一个AR辅助装配应用, "
                f"然后在blender中创建一个阶梯形零件，不需要保存"
                f"并创建一张拧螺丝的图片",
        role="user",
    )

    asyncio.run(multi_agent_task(msg))

    # test
    # asyncio.run(process_agent_tool("请你为我创建一份反推堵盖的安装工艺文件", "./data/img/反推堵盖1.png"))
    # asyncio.run(unity_agent_tool("你好！帮我在unity里创建一个AR辅助装配应用, ", {"工序1": ["工步1", "工步2"]}))
    # asyncio.run(blender_agent_tool("你好！帮我在blender里创建一个1x1x1的立方体"))
    # asyncio.run(creating_blender_agent())
    # print(asyncio.run(get_json(r"asfdsafd{a:1, b:{c:1}}{}aaassd{a:1}dfsa")))
