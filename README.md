# SubmitLens

大学生竞赛与课程交付的本地工作台。当前完成阶段 4：项目管理、任务解析与要求确认、成果关联、自动预检及人工复核。成果验收页展示证据覆盖和检查结果；交付中心仍为不可操作占位。

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

报告和 ZIP 导出；无登录或云存储。本次止于阶段 4。


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

## 阶段 4：预检与人工复核

启动方式不变，更新依赖后重启后端：`pip install -r backend/requirements.txt`（或上文 uv 命令）。新增 mutagen 1.47.0，以纯 Python 读取 MP4 元数据，无 ffmpeg 系统依赖。

在成果页选定文件后点击「开始预检」。只处理已确认、非 stale 的要求，未检查显示「待检查」。列表按失败、待复核、待检查、通过排序，可按验收状态或证据覆盖筛选。每条显示实际、要求、引文、来源、时间与检查结果；支持人工「符合 / 不符合 / 暂不复核」和备注。

- 自动检查仅限存在、扩展名、PDF 页数、MP4 时长、选定文件数量。扩展名检查不证明文件内容真实。
- 页数支持明确页单位；时长支持分钟/秒的区间、上限/下限和精确值；数字支持阿拉伯数字及百以内常用中文数字。混合分钟/秒表达和未识别文本进入待复核，不猜默认值。
- 文件数量必须有原文文件/份/张等明确依据；「至少三组 Prompt 链」不能按三份文件自动通过。内容要求需人工复核。
- 自动失败优先于人工确认；读取异常保持待复核。建议项不改变必交项目总体状态。必要复核完成且适用检查通过后才显示通过。
- 选择变化、替换、删除或解绑使相关人工结论失效；已检查的当前正式要求立即重检。未检查项目保持待检查。编辑要求清除旧结果并回到草稿；任务原文变化的 stale 要求退出验收。
- 检查结果与人工复核在 SQLite 要求 JSON 内保存，项目状态从当前要求计算，刷新/进程重启后仍保留。没有新增哈希、版本历史或规则 DSL。

新增 API：GET `/api/projects/{id}/checks`、POST `/api/projects/{id}/check`、PUT `/api/projects/{id}/requirements/{rid}/review`（`{decision:"pending|pass|fail",note:"..."}`）。

本地引文修复不发模型请求：系统按精确引文搜索来源片段，唯一匹配覆盖模型自造的 ref；每个约束有自己的 source_ref。无法定位或匹配多处返回具体错误，保留原文和已有要求。真实保存响应中 2 条约束唯一定位，21 条匹配重复章节；完整响应仍因歧义拒绝，不冒充全部修复成功，也不凭空补造源文未出现的条款。

实际命令与结果（2026-11-06）：

```powershell
.venv/Scripts/python backend/check_phase1.py
.venv/Scripts/python -m backend.check_phase2
.venv/Scripts/python -m backend.check_phase3
.venv/Scripts/python -m backend.check_phase4
cd frontend
npm run typecheck
npm run build
$env:APP_URL='http://127.0.0.1:5174'
npx playwright test --reporter=line
```

以上退出码均为 0；阶段 2/3 各 2 tests OK，阶段 4 为 4 tests OK；Playwright 5 passed（5.3s）。实际本地 MP4 元数据为 150.448 秒，按 5–8 分钟实际预检不通过。9:21/7:12 是明确的时长替身，不代表实测视频语义；PDF 30/31 页由测试生成。详见 docs/phase4-acceptance.md 与 docs/prompts/phase4.md。

本阶段没有读取 API 密钥、没有新发付费请求。第五阶段仍需实现真实材料 ZIP、报告和导出后材料变更提示，当前交付中心继续不可用。

## 重复章节引用处理更新

现在提取引用异常不会阻断整个清单：不能唯一定位的条目保存为「出处待处理」草稿，列出实际章节和候选来源；点击编辑、选择正确片段并保存后再次核对。整单确认跳过待处理条目，其他有效条目可独立确认。系统用精确引文和实际章节核对候选，不选择首个匹配，也不把国赛条款自动归入省赛。Prompt 已调整为实际交付条款、不同阶段分列，尚未重新付费验证 Prompt 效果。

离线真实响应已生成5条可编辑草稿，选择省赛视频出处后约束均定位至省赛；离线回归2 tests OK、既有检查通过、浏览器6 passed、类型/构建成功。详情见 [引用消歧记录](docs/citation-disambiguation.md)。此前章节中的整单502说明为历史行为。
