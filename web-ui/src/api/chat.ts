import { API_BASE_URL } from "../config"

/** 把用户消息发给 Python Agent 的 POST /chat，返回 reply。 */
export async function sendChat(message: string): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    })
  } catch {
    throw new Error("无法连接订单助手，请确认服务已启动。")
  }

  if (!response.ok) {
    throw new Error("订单助手暂时无法回答，请稍后再试。")
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new Error("订单助手返回了无法解析的响应。")
  }

  if (!isChatResponse(payload)) {
    throw new Error("订单助手返回了无法解析的响应。")
  }

  return payload.reply
}

function isChatResponse(payload: unknown): payload is { reply: string } {
  return (
    typeof payload === "object" &&
    payload !== null &&
    "reply" in payload &&
    typeof payload.reply === "string"
  )
}
