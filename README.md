# SubmitLens

大学生竞赛与课程交付的本地工作台。当前仅完成阶段 1：项目创建、打开、重命名、删除，以及任务说明的编辑、保存和再次读取。成果验收、交付中心为不可操作的导航占位。

## 启动（Windows PowerShell）

环境：Python 3.12、Node.js 22、npm 10。React + TypeScript + Vite，FastAPI + SQLite。从仓库根目录执行：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
cd frontend
npm ci
npm run dev
```

打开终端打印的本地链接，默认 http://127.0.0.1:5173。Vite 将 /api 代理到 8000；前端端口被占用时会选择下一端口。

若本机 Python 的 ensurepip 不可用，可使用已安装的 uv：

```powershell
uv --cache-dir .uv-cache venv .venv --allow-existing
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
```

阶段 1 无环境变量、API Key 或云配置，不提供空的 .env.example。SQLite 首次启动生成在仓库 data/submitlens.sqlite3，位置不依赖启动目录。数据、依赖、构建和测试截图不纳入 Git；需求、设计和协作记录纳入 Git。

## 使用

1. 新建项目，填写名称，选择竞赛或课程，在列表打开。
2. 在「粘贴文本」中输入含段落的说明，点击「保存」。
3. 刷新页面或重启后端，再次打开检查原文。
4. 返回列表可重命名或删除；删除需确认。

未保存文本在页面内返回和刷新/关闭时会提示。URL 的 #project=项目ID 可直接打开项目。

## 检查

```powershell
# 根目录；临时 SQLite，端口 8011，实际重启后端进程
.venv/Scripts/python backend/check_phase1.py
cd frontend
npm run typecheck
npm run build
# 前后端启动后
npx playwright install chromium
npx playwright test --reporter=line
# 前端非默认端口时
$env:APP_URL='http://127.0.0.1:5174'
npx playwright test --reporter=line
```

2026-11-05 实测：类型检查、构建成功；health 返回 status ok；后端进程重启后两类项目与空行/缩进原文保留，改名成功，删除后详情 404；浏览器 1 passed，覆盖创建、保存、刷新、改名、删除，375px 无横向溢出。已查看桌面任务页、移动项目列表截图。真实问题见 docs/prompts/phase1.md。

## API

- GET /api/health
- GET / POST /api/projects；POST 输入 {name,kind}，kind 为 contest/course。
- GET / PATCH / DELETE /api/projects/{id}；PATCH 修改名称/类型。
- PUT /api/projects/{id}/task；输入 {task_source:"paste",task_text:"原文"}。

## 未实现

文档上传与解析、AI 提取、要求清单、成果上传与关联、自动检查、人工复核、报告和 ZIP 导出；无登录或云存储。完整规划见 docs/PRD.md。本次止于阶段 1。
