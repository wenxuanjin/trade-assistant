# python-agent

Trade Assistant 的 Python Agent。项目目标、三进程启动方式和测试分类见仓库根目录 [README.md](../README.md)。

本目录的启动命令：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

工具通过 HTTP 调用 `trade-service`。页面在 `web-ui`。本目录早先的说明要求 Python 3.11 及以上；仓库里没有 `python_requires`。
