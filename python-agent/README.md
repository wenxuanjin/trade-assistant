# python-agent

最小可运行的 Python Agent：FastAPI + LangGraph + 一个查订单工具。没有数据库、Redis、Docker 或前端。

## 启动

需要 Python 3.11+。当前仓库已有 `venv` 和 `.env` 时，直接：

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

从零开始：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

交互文档：<http://127.0.0.1:8000/docs>

## 调用

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"查一下订单 ORD-1001"}'
```

内置两条假订单：`ORD-1001`（已发货）、`ORD-1002`（待处理）。数据写在 `app/tools.py`。
