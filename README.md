# SubmitLens

大学生竞赛与课程交付的本地工作台。当前完成阶段 3：项目管理、任务解析与要求编辑确认、成果文件库和证据关联。成果验收页当前展示证据覆盖；交付中心仍为不可操作占位。

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

自动检查、人工复核、报告和 ZIP 导出；无登录或云存储。本次止于阶段 3。


## 阶段 2 配置与使用

复制 `.env.example` 为根目录 `.env`，填写 `LLM_API_KEY`，并按提供商设置 `LLM_BASE_URL`（兼容接口根地址，包含 /v1）和 `LLM_MODEL`。重启后端生效。Key 仅后端读取，不进入前端构建。无 Key 可直接手动添加要求。

启动命令与上方一致，先重新安装 backend/requirements.txt。上传 PDF/DOCX/MD/TXT，单文件上限 50 MB；扫描 PDF 不做 OCR。TXT/MD 支持 UTF-8 和 GB18030。文档原文及来源片段存 SQLite，不保存原始二进制。解析失败不替换已有原文。编辑解析文本后重新保存会按当前段落建立来源，不伪称编辑后的文字仍对应原 PDF 页码。

点击「整理要求」将当前已保存文本发送至配置的模型服务。首次返回要求为 AI 草稿；重复整理需明确点击「替换未确认 AI 草稿」，仅替换未编辑、未确认的 AI 草稿，保留手工编辑与曾确认的要求；可编辑、新增、删除、拆分，勾选多项后合并。「拆分」表单中修改原要求并填写拆出要求；保存一次完成两项。约束可单独编辑。点击「确认清单」整单确认；编辑要求会回到草稿；任务原文变化使旧要求标为「原文已变，需处理」，整单确认跳过它们。核对当前原文并编辑保存后才能重新确认。

新增接口：POST task-file、POST extract、GET/POST requirements、PUT/DELETE requirements/{rid}、POST requirements-transform（事务拆分/合并）、POST confirm，均位于 /api/projects/{id}/ 下。

测试依赖与命令（仓库根目录）：

```powershell
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe -r backend/requirements-dev.txt
.venv/Scripts/python -m backend.check_phase2
```

2026-11-06：阶段 1 重启检查通过；阶段 2 集成检查通过，覆盖四种格式、超限/损坏不覆盖原文、无 Key、断网、空/无出处响应、AI 草稿、编辑确认、重新打开数据库及拆分合并。浏览器 3 passed（4.9s），类型检查和构建通过。没有进行真实付费 LLM 调用，也未使用仓库未提供的完整赛道原文件作人工验收；引用定位检查不能证明模型理解正确。

阶段 2 执行与协作记录：docs/prompts/phase2.md。阶段 1 记录保留，供对照。

## 阶段 3：成果与证据覆盖

启动命令、端口及依赖不变。进入项目后点击「成果验收」：先点要求直接「上传成果」，或「从文件库选择」已有文件。也可用项目文件库「批量上传成果」。单件要求只能选定一份提交文件；含 file_count 数量约束的要求允许多选，同一文件不重复计数。

文件库展开文件可反向跳转对应要求、下载、替换或删除。替换使用新 ID，保留关联但清除选定状态，需重新选择。取消关联保留原文件；删除文件移除其全部关联；删除项目清理全部成果。原文件以内部 UUID 存于 data/artifacts/，原名仅用于展示和下载，同名不覆盖。不解压或执行文件。

图片上限 20 MB；文档/文本上限 50 MB；视频、ZIP 及其他成果上限 1 GB（按 1024 进位）。成果每次最多读取 1 MiB 分块写盘，失败清理本次请求写入文件；一批中任一失败会取消整批。上传显示进度，100% 后仍可能等待服务端保存完成。任务文档上限保持 50 MB。

覆盖统计仅包含已确认且无需处理的要求，分为「已有选定文件」和「尚未选定文件」。有候选文件但未选定仍算缺少证据；草稿和旧原文要求单列，不进入统计。当前仅是覆盖状态，没有页数/时长或内容有效性结论。

新增 API（前缀 /api/projects/{id}）：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET / POST | /artifacts | 文件库 / multipart files 批量上传 |
| POST | /artifacts?requirement_id={rid} | 定向上传并关联 |
| POST | /artifacts?replace_id={aid} | 单文件替换，生成新 ID，关联不继承选定 |
| GET | /artifacts/{aid}/content | 下载文件 |
| DELETE | /artifacts/{aid} | 删除文件及关联 |
| PUT | /requirements/{rid}/artifacts/{aid} | {} 关联去重；{selected:true/false} 选择/取消选择 |
| DELETE | /requirements/{rid}/artifacts/{aid} | 取消关联 |

文件库响应包含每个文件对应的 requirement_id 与 selected，实现双向查看。所有接口限定当前项目。

2026-11-06 最终实际命令与结果：

- `.venv/Scripts/python backend/check_phase1.py`：退出码 0。
- `.venv/Scripts/python -m backend.check_phase2`：2 tests OK，包含旧要求重确认及 AI 草稿替换回归。
- `.venv/Scripts/python -m backend.check_phase3`：2 tests OK，包含真实后端进程重启、同名内容隔离、多对多去重、选择、替换、取消关联、删除、失败清理和项目清理。
- `npm run typecheck`、`npm run build`（frontend 下）：成功，30 modules。
- `$env:APP_URL='http://127.0.0.1:5174'; npx playwright test --reporter=line`（frontend 下）：4 passed，5.1s，含既有流程与成果双向追踪；已审查桌面与 375px 截图。
- 本地 test 中 Markdown 32,299 B、视频 61,718,568 B、PDF 229,387 B 试传均为 201；清理后剩余成果文件 0。未上传真实 1 GB 文件，超限/中断清理分支以定向集成测试覆盖。

真实 DeepSeek 提取已按用户授权执行一次，但因模型生成不存在的来源行号范围而被拒绝入库，extract 返回 502，不能称为通过。源 Markdown 有 5–8 分钟和 PDF ≤30 页，但无至少 2 分钟 AI 开发、至少 3 组 Prompt 链条款；推荐选题未进入模型返回的必交项。详情及剩余问题见 docs/phase3-acceptance.md。

信息架构参考 [JanusTrace](https://github.com/yesilzeytin/JanusTrace) 的覆盖与追踪呈现，只借鉴思路，未复制、修改或分发其源码；未引入其他候选项目。阶段三原始用户/可见回复见 docs/prompts/phase3-conversation.md，真实修复往返与命令记录见 docs/prompts/phase3.md。test/（含密钥）、data/（含原始模型响应）均不追踪、不提交。
