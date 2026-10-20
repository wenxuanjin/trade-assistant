import { afterEach, describe, expect, it, vi } from "vitest"
import { sendChat } from "./chat"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("sendChat", () => {
  it("把非 2xx 响应显示为友好错误，不展示响应正文", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: "Traceback: secret sk-test" }),
      }),
    )

    await expect(sendChat("查一下订单 ORD-1001")).rejects.toThrow(
      "订单助手暂时无法回答，请稍后再试。",
    )
  })
})
