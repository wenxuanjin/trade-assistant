"""FastAPI entry. Like @SpringBootApplication plus @RestController.

Routes stay thin: validate the body, call the agent, return the reply.
graph.invoke is synchronous, so these handlers are plain def, not async def.
FastAPI runs them in a threadpool.
"""

from fastapi import FastAPI

from app.agent import run_agent
from app.schemas import ChatRequest, ChatResponse

app = FastAPI(title="python-agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    return ChatResponse(reply=run_agent(body.message))
