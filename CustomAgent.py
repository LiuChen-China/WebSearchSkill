from turtle import speed
from agentscope.agent import ReActAgent, AgentBase
from agentscope.formatter import OpenAIChatFormatter
from agentscope.token import CharTokenCounter
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.message import TextBlock, ToolUseBlock
from agentscope.memory import InMemoryMemory
import asyncio
import os
from agentscope.tool import ToolResponse, Toolkit, execute_python_code
import requests
import platform
from copy import deepcopy
from HotReloadConfig import config
from pydantic import BaseModel, Field
import json

# def crawlArticles(count=10)->ToolResponse:
#     '''
#     获取所有股票帖子的标题和链接，当用户询问股票帖子相关问题时必须调用此工具
#     :param count: 获取的股票帖子数量，默认10条
#     '''
#     text = '''
#     #标题1: 春节联欢，全场休市
#     https://www.baidu.com
#     '''
#     return ToolResponse(content=[TextBlock(type="text",text=text)])


# toolkit = Toolkit()
# toolkit.create_tool_group(group_name="stock_tools",description="股票相关工具",active=True,)
# toolkit.register_tool_function(crawlArticles,group_name="stock_tools")
# print(json.dumps(toolkit.get_json_schemas(), indent=4, ensure_ascii=False))




class CustomAgent(ReActAgent):
    '''自定义智能体，沿用ReActAgent的行为功能，主要改写 打印/输出 消息的逻辑'''
    def __init__(self,name,sys_prompt,model,
        formatter,
        toolkit = None,
        parallel_tool_calls = False,
        enable_rewrite_query = True,
        max_iters = 10,
        compression_config = None,
        memory = InMemoryMemory(),
        **kwargs
        ) -> None:
        super().__init__(
            name=name,sys_prompt=sys_prompt,model=model,
            toolkit=toolkit,formatter=formatter,parallel_tool_calls=parallel_tool_calls,
            enable_rewrite_query=enable_rewrite_query,max_iters=max_iters,
            compression_config=compression_config,memory=memory,**kwargs)
        self.msg_queue = asyncio.Queue()

    def _reset_chunks(self):
        '''每次聊天需要 重置一些内部变量'''
        self.last_msg_id = None
        self.stack_think = ''
        self.stack_content = ''
        self.chunks = []

    async def print(self,msg: Msg,last: bool = True,speech = None) -> None:
        '''重写ReActAgent的print方法，原方法每次接收到chunk会打印到控制台'''
        chunk = msg.content[-1]#当前最新的块
        #第一个回复块
        if self.last_msg_id is None:
            self.last_msg_id = msg.id
        #回复id变更，说明是新的回复
        if msg.id != self.last_msg_id:
            self.last_msg_id = msg.id
            self.stack_think = ''
            self.stack_content = ''
        #计算增量
        if chunk['type'] == 'thinking':
            delta_content = chunk['thinking'][len(self.stack_think):]
            self.stack_think = chunk['thinking']
            delta_chunk = {'type':'thinking','delta':delta_content,'stack':self.stack_think,'is_last':last}
        elif chunk['type'] == 'text':
            delta_content = chunk['text'][len(self.stack_content):]
            self.stack_content = chunk['text']
            delta_chunk = {'type':'text','delta':delta_content,'stack':self.stack_content,'is_last':last}
        #工具调用块 只放入最终完整的工具调用块
        else:
            if last:
                chunk['is_last'] = last
                delta_chunk = chunk
            else:
                return 
        if last:
            self.chunks.extend(msg.content)
        await self.msg_queue.put(delta_chunk)

    async def stream_reply(self, msg: Msg | list[Msg]):
        """
        修复版：真正实时流式输出
        1. 后台运行智能体 call
        2. 队列来一个吐一个，不等待任务结束
        3. 任务结束后，吐完队列剩余内容再退出
        """
        self._reset_chunks()
        # 后台运行智能体推理
        call_task = asyncio.create_task(self(msg))

        try:
            while True:
                # 同时监听：队列消息 / 任务完成
                queue_get_task = asyncio.create_task(self.msg_queue.get())
                done, pending = await asyncio.wait(
                    [queue_get_task, call_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # ✅ 情况1：队列有新消息 → 立刻输出
                if queue_get_task in done:
                    delta_chunk = queue_get_task.result()
                    yield delta_chunk
                    self.msg_queue.task_done()

                # ✅ 情况2：智能体任务结束
                if call_task in done:
                    # 吐干净队列里剩下的所有消息
                    while not self.msg_queue.empty():
                        delta_chunk = self.msg_queue.get_nowait()
                        yield delta_chunk
                        self.msg_queue.task_done()
                    break

        except asyncio.CancelledError:
            print("\n[智能体已中断]")
            raise
        finally:
            # 安全清理
            while not self.msg_queue.empty():
                try:
                    self.msg_queue.get_nowait()
                    self.msg_queue.task_done()
                except asyncio.QueueEmpty:
                    break

    async def full_reply(self, msg: Msg | list[Msg]):
        """
        非流式输出：一次性返回完整的 chunks 结果
        """
        self._reset_chunks()
        # 执行完整推理
        await self(msg)
        # 直接返回你维护的完整 chunks
        return self.chunks


############################################模型配置##############################################
model = OpenAIChatModel(
    model_name=config.llm.model,
    stream=True,
    api_key="none",
    client_kwargs={"base_url": config.llm.openai_api},
    generate_kwargs={
        "temperature": 0.3, 
        "max_tokens": 8000,"stream":True,
        "extra_body": {
            "enable_thinking": True,
            }
    }
)
#################################################################################################

############################################记忆压缩配置##############################################
# 指导压缩的自定义提示
compression_prompt='''请总结上述对话，重点关注主题、关键讨论点和待完成任务。'''
# 结构化摘要的自定义 schema
class CustomSummary(BaseModel):
    main_topic: str = Field(max_length=200,description="对话的主题")
    key_points: str = Field(max_length=400,description="讨论的重要观点")
    pending_tasks: str = Field(max_length=200,description="待完成的任务")
#格式化摘要的自定义模板 使用 summary_schema 中定义的字段作为占位符
summary_template='''
对话摘要：
主题：{main_topic}\n\n
关键观点：\n{key_points}\n\n
待完成任务：\n{pending_tasks}
'''
# 记忆压缩配置
compression_config=ReActAgent.CompressionConfig(
    trigger_threshold=100000,
    keep_recent=12,
    summary_schema=CustomSummary,
    compression_prompt=compression_prompt,
    agent_token_counter=CharTokenCounter(),
    summary_template=summary_template,enable=True
)
#################################################################################################
name = '网页信息提取爬虫'
sys_prompt = '''
# 角色
你是思维敏捷的智能网页信息提取爬虫，仅依据网页标题和网页原文内容，精准抽取有效核心信息。

# 要求
1.精准过滤剔除：广告文案、无效乱码、HTML 标签、无关冗余话术、无意义符号、与标题主题无关的所有冗余内容。
2.网页中所有表格、行列结构内容，统一转换为键值对格式，格式固定为：表头 1：单元格内容；表头 2：单元格内容。
3.纯文本内容保留原意，精简冗余语句，只留存和标题强相关的有效正文。
4.全程只输出提取后的纯净结果，禁止输出解释、打招呼、思考过程、多余备注等任何额外内容。
5.严格遵循示例格式，不改动输出结构、不新增标点、不额外换行冗余。

# 示例
## 输入
标题：
KFC的美式咖啡有哪些
网页内容：
KFC的美式咖啡是一种传统的咖啡，由咖啡豆、糖、牛奶和水组成。
<tr>
    <th>咖啡名</th>
    <th>价格</th>
</tr>
<tr>
    <td>柠檬咖啡</td>
    <td>18</td>
</tr>
<tr>
    <td>叶子咖啡</td>
    <td>17</td>
</tr>
## 输出
KFC的美式咖啡是一种传统的咖啡，由咖啡豆、糖、牛奶和水组成。
咖啡名：柠檬咖啡；价格：18
咖啡名：叶子咖啡；价格：17
'''
agent = CustomAgent(
    name=name,
    sys_prompt=sys_prompt,
    model=model,
    toolkit=None,
    compression_config=compression_config,
    formatter=OpenAIChatFormatter(),
)

async def extractWebInfo(title: str, content: str) -> list:
    """
    从网页标题和内容中提取有效核心信息
    :param title: 网页标题
    :param title: 网页原文内容
    :return: 提取后的有效核心信息
    """
    msgs = [
        Msg(name="user", content=f"标题：{title}\n网页内容：{content}", role="user"),
    ]
    return await agent.full_reply(msgs)


if __name__ == '__main__':
    async def discussArticle() -> None:
        """使用推理模型的示例。"""
        msgs = [
            Msg(name="assistant", content='你好你好', role="assistant"),
            Msg(name="user", content="有没有股票帖子", role="user"),
        ]
        # print("=" * 50)
        # print("【1】流式输出（实时chunk）")
        # print("=" * 50)
        # async for chunk in agent.stream_reply(msgs):
        #     print(chunk)

        print("\n" + "=" * 50)
        print("【2】非流式输出（完整结果）")
        print("=" * 50)
        full_result = await agent.full_reply(msgs)
        print(full_result)

    asyncio.run(discussArticle())


