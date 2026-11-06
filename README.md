# SubmitLens

大学生竞赛与课程交付的本地工作台。当前完成阶段 2：项目管理、任务说明文本/文件解析、要求草稿提取、编辑与确认持久化。成果验收、交付中心为不可操作的导航占位。

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

阶段 2 可选配置见下方。SQLite 首次启动生成在仓库 data/submitlens.sqlite3，位置不依赖启动目录。数据、依赖、构建和测试截图不纳入 Git；需求、设计和协作记录纳入 Git。

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

成果上传与关联、自动检查、人工复核、报告和 ZIP 导出；无登录或云存储。本次止于阶段 2。


## 阶段 2 配置与使用

复制 `.env.example` 为根目录 `.env`，填写 `LLM_API_KEY`，并按提供商设置 `LLM_BASE_URL`（兼容接口根地址，包含 /v1）和 `LLM_MODEL`。重启后端生效。Key 仅后端读取，不进入前端构建。无 Key 可直接手动添加要求。

启动命令与上方一致，先重新安装 backend/requirements.txt。上传 PDF/DOCX/MD/TXT，单文件上限 50 MB；扫描 PDF 不做 OCR。TXT/MD 支持 UTF-8 和 GB18030。文档原文及来源片段存 SQLite，不保存原始二进制。解析失败不替换已有原文。编辑解析文本后重新保存会按当前段落建立来源，不伪称编辑后的文字仍对应原 PDF 页码。

点击「整理要求」将当前已保存文本发送至配置的模型服务。返回要求追加为草稿，不覆盖已有清单；可编辑、新增、删除、拆分，勾选多项后合并。「拆分」表单中修改原要求并填写拆出要求；保存一次完成两项。约束可单独编辑。点击「确认清单」整单确认；编辑要求或更新任务原文会使相应确认状态回到草稿。

新增接口：POST task-file、POST extract、GET/POST requirements、PUT/DELETE requirements/{rid}、POST requirements-transform（事务拆分/合并）、POST confirm，均位于 /api/projects/{id}/ 下。

测试依赖与命令（仓库根目录）：

```powershell
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe -r backend/requirements-dev.txt
.venv/Scripts/python -m backend.check_phase2
```

2026-11-06：阶段 1 重启检查通过；阶段 2 集成检查通过，覆盖四种格式、超限/损坏不覆盖原文、无 Key、断网、空/无出处响应、AI 草稿、编辑确认、重新打开数据库及拆分合并。浏览器 3 passed（4.9s），类型检查和构建通过。没有进行真实付费 LLM 调用，也未使用仓库未提供的完整赛道原文件作人工验收；引用定位检查不能证明模型理解正确。

阶段 2 执行与协作记录：docs/prompts/phase2.md。阶段 1 记录保留，供对照。
