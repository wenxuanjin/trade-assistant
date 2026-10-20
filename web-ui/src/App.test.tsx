import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import App from "./App"
import { sendChat } from "./api/chat"

vi.mock("./api/chat", () => ({
  sendChat: vi.fn(),
}))

const sendChatMock = vi.mocked(sendChat)

beforeEach(() => {
  sendChatMock.mockReset()
})

afterEach(() => {
  cleanup()
})

describe("订单助手对话", () => {
  it("发送输入框中的消息并展示回复", async () => {
    sendChatMock.mockResolvedValue("订单金额是 599.00。")
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByRole("textbox", { name: "消息" }), "查一下订单 ORD-1001")
    await user.click(screen.getByRole("button", { name: "发送" }))

    expect(sendChatMock).toHaveBeenCalledTimes(1)
    expect(sendChatMock).toHaveBeenCalledWith("查一下订单 ORD-1001")
    expect(await screen.findByText("订单金额是 599.00。")).toBeTruthy()
  })

  it("快捷提问会把既定问题发给助手", async () => {
    sendChatMock.mockResolvedValue("流程已发货，尚未送达。")
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole("button", { name: /交易流程/ }))

    expect(sendChatMock).toHaveBeenCalledWith("ORD-1001 的交易流程怎么样？为什么还没送达？")
    expect(await screen.findByText("流程已发货，尚未送达。")).toBeTruthy()
  })

  it("请求进行中显示加载状态，并且不能重复提交", async () => {
    let resolveReply: (reply: string) => void = () => {}
    sendChatMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveReply = resolve
        }),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByRole("textbox", { name: "消息" }), "查一下订单 ORD-1001")
    await user.click(screen.getByRole("button", { name: "发送" }))

    expect(screen.getByText("正在查询…")).toBeTruthy()
    expect((screen.getByRole("button", { name: "发送中" }) as HTMLButtonElement).disabled).toBe(true)
    await user.click(screen.getByRole("button", { name: "发送中" }))
    expect(sendChatMock).toHaveBeenCalledTimes(1)

    resolveReply("已收到。")
    expect(await screen.findByText("已收到。")).toBeTruthy()
  })

  it("请求失败时显示错误，并允许重新发送", async () => {
    sendChatMock
      .mockRejectedValueOnce(new Error("无法连接订单助手，请确认服务已启动。"))
      .mockResolvedValueOnce("订单金额是 599.00。")
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole("button", { name: /订单金额/ }))

    expect((await screen.findByRole("alert")).textContent).toContain(
      "无法连接订单助手，请确认服务已启动。",
    )
    await user.click(screen.getByRole("button", { name: "重新发送" }))

    expect(sendChatMock).toHaveBeenCalledTimes(2)
    expect(sendChatMock).toHaveBeenNthCalledWith(2, "订单 ORD-1001 的金额是多少？")
    expect(await screen.findByText("订单金额是 599.00。")).toBeTruthy()
  })

  it("清空对话会移除已有消息", async () => {
    sendChatMock.mockResolvedValue("订单金额是 599.00。")
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole("button", { name: /支付渠道/ }))
    expect(await screen.findByText("订单金额是 599.00。")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "清空对话" }))

    expect(screen.queryByText("订单金额是 599.00。")).toBeNull()
    expect(screen.getByRole("heading", { name: "欢迎使用订单助手" })).toBeTruthy()
  })
})
