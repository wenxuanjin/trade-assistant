import { useEffect, useRef, useState } from "react"
import type { KeyboardEvent, ReactNode } from "react"
import { sendChat } from "./api/chat"
import {
  IconChat,
  IconClock,
  IconCoin,
  IconDoc,
  IconFlow,
  IconFolder,
  IconHelp,
  IconLayout,
  IconMenu,
  IconMoon,
  IconPay,
  IconPlus,
  IconSearch,
  IconSend,
  IconSettings,
  IconSun,
  IconUsers,
  LogoMark,
} from "./icons"

const QUICK_QUESTIONS = [
  {
    title: "订单金额",
    message: "订单 ORD-1001 的金额是多少？",
    tone: "amber",
    icon: <IconCoin />,
  },
  {
    title: "交易流程",
    message: "ORD-1001 的交易流程怎么样？为什么还没送达？",
    tone: "blue",
    icon: <IconFlow />,
  },
  {
    title: "支付渠道",
    message: "ORD-1001 的支付渠道是什么？",
    tone: "green",
    icon: <IconPay />,
  },
] as const

const NAV_ITEMS: { label: string; icon: ReactNode; current?: boolean; badge?: string }[] = [
  { label: "对话", icon: <IconChat />, current: true },
  { label: "项目", icon: <IconFolder /> },
  { label: "模板", icon: <IconLayout /> },
  { label: "文档", icon: <IconDoc /> },
  { label: "社区", icon: <IconUsers />, badge: "NEW" },
  { label: "历史", icon: <IconClock /> },
]

type Role = "user" | "assistant"
type Theme = "light" | "dark"

type ChatMessage = {
  id: number
  role: Role
  text: string
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState("")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [failedMessage, setFailedMessage] = useState<string | null>(null)
  const [theme, setTheme] = useState<Theme>("light")
  const [navOpen, setNavOpen] = useState(false)
  const nextId = useRef(1)
  const listEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ block: "end" })
  }, [messages, sending, error])

  function appendMessage(role: Role, text: string) {
    const id = nextId.current
    nextId.current += 1
    setMessages((current) => [...current, { id, role, text }])
  }

  async function ask(message: string, alreadyShown: boolean) {
    const text = message.trim()
    if (!text || sending) {
      return
    }

    setError(null)
    setFailedMessage(null)
    setSending(true)
    setNavOpen(false)
    if (!alreadyShown) {
      appendMessage("user", text)
      setDraft("")
    }

    try {
      const reply = await sendChat(text)
      appendMessage("assistant", reply)
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "发送失败。"
      setFailedMessage(text)
      setError(detail)
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void ask(draft, false)
    }
  }

  function clearConversation() {
    if (sending) {
      return
    }
    setMessages([])
    setDraft("")
    setError(null)
    setFailedMessage(null)
  }

  const showWelcome = messages.length === 0 && !sending && !error

  return (
    <div className="canvas">
      <div className={`shell ${navOpen ? "nav-open" : ""}`} data-theme={theme}>
        <aside className="sidebar">
          <div className="brand">
            <LogoMark />
            <strong>订单助手</strong>
          </div>

          <label className="search">
            <IconSearch />
            <input placeholder="搜索" aria-label="搜索" />
            <kbd>⌘K</kbd>
          </label>

          <nav className="nav" aria-label="主导航">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.label}
                type="button"
                className={item.current ? "nav-item current" : "nav-item"}
                aria-current={item.current ? "page" : undefined}
                disabled={!item.current}
              >
                {item.icon}
                <span>{item.label}</span>
                {item.badge && <em className="badge">{item.badge}</em>}
              </button>
            ))}
            <p className="nav-label">设置与帮助</p>
            <button type="button" className="nav-item" disabled>
              <IconSettings />
              <span>设置</span>
            </button>
            <button type="button" className="nav-item" disabled>
              <IconHelp />
              <span>帮助</span>
            </button>
          </nav>

          <div className="sidebar-foot">
            <div className="theme-switch" role="group" aria-label="主题">
              <button
                type="button"
                className={theme === "light" ? "active" : ""}
                onClick={() => setTheme("light")}
              >
                <IconSun />
                浅色
              </button>
              <button
                type="button"
                className={theme === "dark" ? "active" : ""}
                onClick={() => setTheme("dark")}
              >
                <IconMoon />
                深色
              </button>
            </div>
            <div className="account">
              <span className="avatar" aria-hidden="true">助</span>
              <span>
                <strong>本地演示</strong>
                <small>订单查询</small>
              </span>
            </div>
          </div>
        </aside>

        {navOpen && (
          <button type="button" className="scrim" aria-label="关闭导航" onClick={() => setNavOpen(false)} />
        )}

        <section className="workspace">
          <header className="topbar">
            <button type="button" className="icon-btn menu-btn" aria-label="打开导航" onClick={() => setNavOpen(true)}>
              <IconMenu />
            </button>
            <h1>对话</h1>
            <div className="top-actions">
              <button
                type="button"
                className="clear-btn"
                onClick={clearConversation}
                disabled={sending || messages.length === 0}
              >
                清空对话
              </button>
            </div>
          </header>

          <div className="stage">
            {showWelcome ? (
              <div className="welcome">
                <h2>欢迎使用订单助手</h2>
                <p>可以查询订单金额、交易流程和支付渠道。不确定从哪开始？</p>
                <div className="cards">
                  {QUICK_QUESTIONS.map((question) => (
                    <button
                      key={question.message}
                      type="button"
                      className="prompt-card"
                      disabled={sending}
                      onClick={() => void ask(question.message, false)}
                    >
                      <span className={`tile ${question.tone}`}>{question.icon}</span>
                      <span className="card-copy">
                        <strong>{question.title}</strong>
                        <small>{question.message}</small>
                      </span>
                      <IconPlus className="card-plus" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="transcript" aria-live="polite">
                {messages.map((message) => (
                  <article key={message.id} className={`bubble ${message.role}`}>
                    <span className="who">{message.role === "user" ? "你" : "助手"}</span>
                    <p>{message.text}</p>
                  </article>
                ))}
                {sending && (
                  <article className="bubble assistant pending">
                    <span className="who">助手</span>
                    <p>正在查询…</p>
                  </article>
                )}
                {error && (
                  <div className="error" role="alert">
                    <p>{error}</p>
                    <button
                      type="button"
                      onClick={() => failedMessage && void ask(failedMessage, true)}
                      disabled={sending || !failedMessage}
                    >
                      重新发送
                    </button>
                  </div>
                )}
                <div ref={listEndRef} />
              </div>
            )}
          </div>

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault()
              void ask(draft, false)
            }}
          >
            <div className="composer-box">
              <label className="sr-only" htmlFor="message">
                消息
              </label>
              <textarea
                id="message"
                rows={2}
                value={draft}
                placeholder="输入问题，Enter 发送，Shift+Enter 换行"
                disabled={sending}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={onKeyDown}
              />
              <button type="submit" className="send" aria-label={sending ? "发送中" : "发送"} disabled={sending || draft.trim().length === 0}>
                <IconSend />
              </button>
            </div>
            <div className="composer-meta">
              <span>回答来自订单助手</span>
              <span>{draft.length}</span>
            </div>
          </form>
        </section>

        <aside className="rail">
          <div className="rail-head">
            <strong>当前会话</strong>
          </div>
          {messages.length === 0 ? (
            <p className="rail-empty">开始提问后，这次对话会显示在这里。</p>
          ) : (
            <article className="session-card">
              <strong>订单查询</strong>
              <p>{messages.find((message) => message.role === "user")?.text}</p>
            </article>
          )}
        </aside>
      </div>
    </div>
  )
}
