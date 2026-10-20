# 测试

仓库里没有 CI 配置。下面的命令来自 `pom.xml`、`requirements.txt` 配套的 `unittest` 测试，以及 `web-ui/package.json` 的 `scripts`。本文不记录通过数量或耗时。

## 怎么区分

| 类别 | 仓库里有没有 | 说明 |
| --- | --- | --- |
| 模拟模型或隔离测试 | 有 | 不调用真实模型 API，不依赖三个进程同时在线 |
| 真实模型评测 | 没有 | 没有任何测试会请求 `OPENAI_BASE_URL`，也没有评分集 |
| 完整端到端测试 | 没有 | 没有同时启动 Browser、Python Agent、真实模型和 Java 服务的自动化测试 |

`python-agent/tests/test_agent_behavior.py` 文件头写明：替身按脚本返回工具调用，最终回答只从工具结果拼接，不能当作真实模型生成能力的证据。

## Java

```bash
cd trade-service
mvn test
```

唯一的测试类是 `src/test/java/com/tradeassistant/controller/OrderControllerTest.java`。它使用 `@SpringBootTest` 和 `@AutoConfigureMockMvc`，在进程内调用控制器，使用 Repository 里的内存数据。它不监听端口，不访问 Python。

九个测试方法覆盖：

- `GET /api/orders/ORD-1001` 与 `ORD-1002`
- 这两个订单的 `/trade-flow` 和 `/trade-account`
- 三个接口查询 `ORD-9999` 时返回 404，正文为 `{"status":404,"message":"Order not found: ORD-9999"}`

## Python

```bash
cd python-agent
source venv/bin/activate
python -m unittest discover -s tests -t .
```

测试框架是标准库 `unittest`。`requirements.txt` 没有 pytest。导入 `app.agent` 或 `app.main` 会读取 `python-agent/.env` 并创建模型客户端；隔离测试把模型和 HTTP 调用替掉，因此不会发出模型请求或 Java 请求。

| 文件 | 替身 | 验证什么 |
| --- | --- | --- |
| `tests/test_get_order.py` | `httpx.get` | 200、404、连接失败、超时、HTTP 500、非法 JSON、缺少或类型不对的必需字段 |
| `tests/test_get_trade_flow.py` | `httpx.get` | 200 字段映射、404 未找到结构、连接失败、超时、HTTP 500、非法 JSON |
| `tests/test_get_trade_account.py` | `httpx.get` | 同上，对象换成支付账户 |
| `tests/test_chat.py` | `run_agent` 或 `graph.invoke` | `/health`、正常 `reply`、空消息和空白消息 422、非法 JSON 422、Agent 异常时的固定 500 正文 |
| `tests/test_agent_behavior.py` | 自定义 `ScriptedAgentModel`，并替换 `httpx.get` | 生产 Agent 图收到预设 tool call 后，是否按名称和参数执行工具，并把工具结果送回下一次模型调用 |

行为测试的五个场景：

1. 「ORD-1001 的金额是多少」调用一次 `get_order`，参数 `order_id=ORD-1001`。
2. 「ORD-1001 为什么还没送达」调用一次 `get_trade_flow`。
3. 金额和支付渠道在同一次模型响应里并行调用 `get_order` 与 `get_trade_account`。
4. 金额、支付渠道和未送达原因分三轮依次调用三个工具，后一轮能看到前面的 `ToolMessage`。
5. 「订单金额是多少」没有订单号。替身直接回答「请提供订单号。」，没有工具调用。测试同时检查发给模型的 system prompt 含有 `If no order id is given, ask for one.`

第 5 项证明的是提示词被送进了模型请求，以及替身不调用工具时链路不会编造 `ORD-`。它不证明真实模型会这样追问。

## 前端

```bash
cd web-ui
npm test
npm run build
```

`npm test` 对应 `vitest run`，环境是 jsdom。`npm run build` 对应 `tsc -b && vite build`。

| 文件 | 替身 | 验证什么 |
| --- | --- | --- |
| `src/App.test.tsx` | `sendChat` | 发送输入、快捷提问原文、加载时不能重复提交、失败后重新发送、清空对话 |
| `src/api/chat.test.ts` | `fetch` 返回 HTTP 500 | 非 2xx 显示固定中文提示，不展示响应正文 |

这些测试不打开浏览器，也不连接 Agent。

## 现有测试没有覆盖的行为

- 真实模型对中文问题的工具选择、追问和措辞。
- 三个进程同时运行时，从页面点击到 Java Mock 数据再回到气泡的整条链路。
- `get_trade_flow` 和 `get_trade_account` 在超时、连接失败和 HTTP 500 时的文案差异。当前实现和测试都把它们收成同一句 `Trade service is unavailable.`
- 本机 HTTP 代理对 `httpx` 访问 `localhost` 的影响。工具使用 httpx 默认代理行为，仓库里没有针对代理的测试。
