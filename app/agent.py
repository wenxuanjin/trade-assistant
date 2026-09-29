"""LangGraph agent. Like a @Service that owns the call flow."""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.config import settings
from app.tools import get_order, get_trade_account, get_trade_flow

# 模块级单例，导入时创建一次。相当于 @Bean。
_llm = ChatOpenAI(
    model=settings.openai_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)

graph = create_agent(
    _llm,
    tools=[get_order, get_trade_flow, get_trade_account],
    system_prompt=(
        "You are an order assistant. "
        "If no order id is given, ask for one. "
        "Answer in the user's language, using only the tool result. "
        "You may call one or more tools when necessary: "
        "1. order status, item, or amount → get_order "
        "2. trade steps, payment/shipping/delivery timeline → get_trade_flow "
        "3. payment account, payer, channel, or account number → get_trade_account"
    ),
)


def run_agent(user_message: str) -> str:
    result = graph.invoke({"messages": [("user", user_message)]})
    content = result["messages"][-1].content
    if isinstance(content, str):
        return content
    return str(content)
