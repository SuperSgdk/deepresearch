# 项目运行与维护

本文记录我维护 DeepResearch 使用的环境要求和运行步骤，运行权限限于作者和获得 SuperSgdk 书面授权的人。公开这些步骤不授予任何软件使用权，授权范围见 [查看许可](../LICENSE)。

建议使用 **Python 3.11、Node.js 24、Docker Compose v2**。需要开通 DashScope 模型/Embedding 和博查搜索服务；这些 API 会产生费用，密钥只写入本地 `.env`。默认模型为 `qwen-plus`。

### 1. 下载和安装

```bash
git clone https://github.com/SuperSgdk/deepresearch.git
cd deepresearch
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c constraints.txt
Copy-Item .env.example .env
Copy-Item deploy/.env.example deploy/.env
```

Linux/macOS：

```bash
.venv/bin/python -m pip install -r requirements.txt -c constraints.txt
cp .env.example .env
cp deploy/.env.example deploy/.env
```

编辑 `.env` 中的 `DASHSCOPE_API_KEY`、`BOCHA_API_KEY`；将两个文件中的 `CHANGE_ME` 改为同一个数据库密码。密码包含特殊字符时，`POSTGRES_DSN` 中的密码需要 URL 编码。

### 2. 构建网页

```bash
cd front/agent_front
npm ci
npm run build
cd ../..
```

### 3. 启动数据库并导入项目说明

先启动 Docker Engine，然后运行：

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --wait
```

Windows：

```powershell
.\.venv\Scripts\python.exe app/mult_agents/rag/ingest.py knowledge
powershell -NoProfile -ExecutionPolicy Bypass -File start.ps1 -NoBrowser
```

Linux/macOS：

```bash
.venv/bin/python app/mult_agents/rag/ingest.py knowledge
.venv/bin/python -m uvicorn app_main:app --app-dir app --host 127.0.0.1 --port 8010
```

打开 [http://127.0.0.1:8010](http://127.0.0.1:8010)。首次启动 Milvus 可能需要等待约 1–2 分钟。资料导入是追加操作，同一文件无需重复导入。

只看网页时，构建后运行 `start.ps1 -WebOnly -NoBrowser`，不需要数据库和密钥；研究请求仍需要完成配置。Windows 用 `stop.ps1` 停止项目并保留数据库卷。Linux/macOS 结束后端进程，再运行 `docker compose --env-file deploy/.env -f deploy/compose.yaml stop`。
