"""HTTP request and response models. Like DTO / VO."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str


class TradeFlowStep(BaseModel):
    """One step in an order's trade timeline."""

    step: int = Field(ge=1)
    name: str
    status: str
    occurred_at: str | None = None


class TradeFlow(BaseModel):
    """Structured trade flow returned by get_trade_flow."""

    order_id: str
    found: bool
    current_status: str
    steps: list[TradeFlowStep] = Field(default_factory=list)


class TradeAccount(BaseModel):
    """Structured trade account returned by get_trade_account."""

    order_id: str
    found: bool
    account_id: str | None = None
    account_name: str | None = None
    payment_channel: str | None = None
    masked_account_no: str | None = None
    currency: str | None = None
