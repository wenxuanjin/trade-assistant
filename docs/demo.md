# 本地演示

演示使用 Java 内存里的两笔订单。下面的 JSON 来自 Repository 和 DTO，不是本次编写文档时对运行中服务的抓包结果。服务启动后，应用下面的 curl 自行核对。

## 准备

1. 在 `trade-service` 执行 `mvn spring-boot:run`。端口是 `8080`。
2. 在 `python-agent` 准备虚拟环境和 `.env`，再执行 `uvicorn app.main:app --reload --port 8000`。`.env` 需要有效的 `OPENAI_API_KEY`，`TRADE_SERVICE_BASE_URL` 使用 `http://localhost:8080`。
3. 在 `web-ui` 执行 `npm install` 和 `npm run dev`，用 `http://localhost:5173` 或 `http://127.0.0.1:5173` 打开。

只想看 Java 数据时，第 2、3 步可以不做。只想看 Agent 接口时，第 3 步可以不做，但第 1 步需要保留，否则工具会告诉模型交易服务不可用。

## 直接查看 Mock 数据

订单：

```bash
curl http://localhost:8080/api/orders/ORD-1001
curl http://localhost:8080/api/orders/ORD-1002
```

`ORD-1001` 的当前数据是状态 `shipped`、商品 `Mechanical Keyboard`、金额 `599.00`。`ORD-1002` 是 `pending`、`USB-C Cable`、`29.00`。

流程和支付账户：

```bash
curl http://localhost:8080/api/orders/ORD-1001/trade-flow
curl http://localhost:8080/api/orders/ORD-1001/trade-account
curl http://localhost:8080/api/orders/ORD-9999
```

不存在的订单返回 HTTP 404：

```json
{"status":404,"message":"Order not found: ORD-9999"}
```

`ORD-1001` 的流程里，`delivered` 步骤是 `pending`。支付渠道是 `alipay`。`ORD-1002` 的支付渠道是 `wechat_pay`。

## 通过 Agent 提问

健康检查不调用模型：

```bash
curl http://127.0.0.1:8000/health
```

成功时正文是 `{"status":"ok"}`。进程能启动，说明导入阶段已经读到了 `OPENAI_API_KEY`。

对话会调用真实模型，也会由工具访问 Java：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"订单 ORD-1001 的金额是多少？"}'
```

成功响应形状是 `{"reply":"..."}`。`reply` 的具体句子由模型生成，本文不预设一句标准答案。

同一接口还可以试：

- `ORD-1001 的交易流程怎么样？为什么还没送达？`
- `ORD-1001 的支付渠道是什么？`
- `订单金额是多少`

最后一句没有订单号。system prompt 要求模型追问。是否真的追问，需要看这次模型返回，仓库测试不能代替这次观察。

空白消息会被拒绝，并且不会进入 Agent：

```bash
curl -i -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":" "}'
```

预期状态码是 422。

Agent 启动后，终端会打印 `USER`、`TOOL CALL`、`TOOL RESULT` 和 `FINAL ANSWER`。工具名应是 `get_order`、`get_trade_flow` 或 `get_trade_account`。这是观察真实模型选择的直接位置。

## 在页面上操作

打开页面后可以：

1. 点一张快捷卡片，确认发出的是卡片上的完整问题，而不是标题。
2. 在输入框输入问题。Enter 发送，Shift+Enter 换行。
3. 等待时按钮变为「发送中」，不能再次点击发送。
4. 看到回复后点「清空对话」，欢迎区重新出现。
5. 停掉 Python Agent 再发送一次，页面应提示「无法连接订单助手，请确认服务已启动。」然后可以用「重新发送」。

浅色和深色切换只影响当前页面状态。侧栏搜索和「对话」以外的导航没有功能。
