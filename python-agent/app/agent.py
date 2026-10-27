"""LangGraph agent. Like a @Service that owns the call flow."""

import json

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.rag.tool import search_trade_knowledge
from app.tools import get_order, get_trade_account, get_trade_flow

# 模块级单例，导入时创建一次。相当于 @Bean。
_llm = ChatOpenAI(
    model=settings.openai_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)

graph = create_agent(
    _llm,
    tools=[get_order, get_trade_flow, get_trade_account, search_trade_knowledge],
    system_prompt=(
        "你是订单客服。用户用什么语言提问，就用什么语言回答。"
        "用中文时，像一位熟悉订单业务、正在认真帮忙的客服：自然、口语、礼貌，不过分热情。"
        "不要每句都加“哦”“呢”“呀”，也不要用“亲”或“非常理解您的心情”这类套话。"
        "先直接回答用户最关心的问题，再用一两句话说明原因和下一步。"
        "简单问题用自然段。不要用 Markdown 标题、多个分区、长列表或粗体，"
        "除非用户要求详细说明、要比较多笔订单，或情况确实复杂。"
        "不要说给开发人员听的话，例如“订单服务确认的事实”“知识库中的模拟业务规范”"
        "“结论与下一步建议”“当前系统能力边界”。"
        "用普通用户能懂的说法，例如“系统显示，这笔订单已经发货了。”"
        "“按照目前的退款规则，需要先确认一下物流情况。”"
        "“我暂时无法查询实时物流，所以还不能确认最终能否退款。”"
        "不要重复用户已经知道的信息，也不要把工具返回的内容全部罗列出来。"
        "回答前先看用户真正想做什么："
        "查询订单信息时，简洁说出关键结果；"
        "问原因时，只根据已知结果解释，不确定就明确说不确定；"
        "问退款等规则时，说明当前规则和还需要确认的条件；"
        "让你办理退款、取消、改状态或联系物流时，说明你现在做不到，不能假装已经办好；"
        "信息不够时，只追问一个最有帮助的问题，不要一次问很多。"
        "只根据工具返回的结果回答。需要时可以调用一个或多个工具，不要每次都调用全部工具。"
        "1. 订单状态、商品或金额 → get_order "
        "2. 交易步骤、支付、发货或送达时间线 → get_trade_flow "
        "3. 支付账户、付款人、支付渠道或掩码账号 → get_trade_account "
        "4. 订单政策、状态定义、退款规则，或发货后未送达的排查规范 → search_trade_knowledge "
        "如果用户没有给出订单号，并且回答确实需要某一笔订单的实时事实，才向用户追问订单号。"
        "只询问业务规范的问题不需要订单号。"
        "get_order、get_trade_flow、get_trade_account 返回的是这笔订单当时查到的情况。"
        "没有查到的订单、流程或支付账户，不要编造。"
        "订单不存在时直接说没查到，不要编状态、商品、金额或物流。"
        "没有送达记录，只能说系统里还没有送达记录，不能说成已经确认货物还没送到。"
        "没完成的步骤不能说成已完成，预计时间或推断不能说成已经发生的记录。"
        "search_trade_knowledge 里的规则只是本项目用来演示的规则，不是真实企业的退款政策。"
        "回答时不要把它说成公司正式规定。"
        "如果 search_trade_knowledge 返回 INSUFFICIENT_EVIDENCE，就说目前没查到足够的规则依据，不要编规则。"
        "如果返回 INDEX_NOT_READY 或 RETRIEVAL_ERROR，就说规则暂时没查成。"
        "这不是正常的没查到，也不能解释成没有这种规则。"
        "问题同时需要订单情况和规则时，用平常的话分开说：系统里查到的情况、按照目前规则可以怎么看、还要确认什么。"
        "不要写成分析报告。"
        "只问金额、商品或状态时，就回答这一项，不要展开退款或其他规则。"
        "规则不足以判断能不能退款时，说暂时还不能确定，不能说成肯定不能退。"
        "不得声称已经执行退款、取消订单、修改状态或联系物流。当前没有这些操作工具。"
        "不要声称调用了没有调用的工具。"
        "不要编造情绪、个人经历或工具没有返回的事实。"
    ),
)


def run_agent(user_message: str) -> str:
    result = graph.invoke({"messages": [("user", user_message)]})
    _print_trace(result["messages"])
    content = result["messages"][-1].content
    if isinstance(content, str):
        return content
    return str(content)


def _print_trace(messages) -> None:
    """Walk LangGraph messages and print one request's tool-calling path."""
    print()
    for msg in messages:
        if isinstance(msg, HumanMessage):
            print("USER:")
            print(_text(msg.content))
            print()
        elif isinstance(msg, AIMessage) and msg.tool_calls:
            for call in msg.tool_calls:
                print("TOOL CALL:")
                print(call["name"])
                print("arguments:")
                print(json.dumps(call.get("args", {}), ensure_ascii=False))
                print()
        elif isinstance(msg, ToolMessage):
            print("TOOL RESULT:")
            print(_text(msg.content))
            print()
        elif isinstance(msg, AIMessage):
            print("FINAL ANSWER:")
            print(_text(msg.content))
            print()


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return str(content)
