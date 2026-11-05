# SubmitLens — 技术约定与开发切分 V1.0

本文只规定 **MVP 已知需要的机制**；新增表、封装、规则语言、校验门禁或测试框架之前，必须有明确失败场景，不为“以后可能用到”而加。

## 1. 技术选型

| 模块 | 技术 | 依据 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 单页工作台、快速迭代 |
| 后端 | Python + FastAPI | 文件接口、文档处理、模型 API 接入 |
| 持久化 | SQLite + 本地目录 | 本地单用户；项目刷新后仍存在 |
| PDF | pypdf | 提取文字、读取页数 |
| DOCX | python-docx | 提取段落 |
| MP4 | mutagen（MP4 元数据） | 获取视频时长，不上传视频到 LLM |
| AI 提取 | 可配置的兼容 OpenAI Chat Completions API | 避免绑定特定云厂商；Key 只存服务端环境变量 |
| 导出 | Python 标准库 zipfile | 生成真实 ZIP + Markdown 报告 |

前后端本地启动。前端请求 `/api` 代理至 FastAPI。无需注册、云数据库或对象存储。首版只自动检查 MP4 视频时长；其他格式视频可存储但不自动判定时长。

## 2. 核心数据对象

采用最直接的四类持久对象，检查子项与检查结果可以作为 JSON 数据保存在要求对象内，不先做通用规则引擎。

### Project

- `id`、`name`、`kind`：`contest | course`
- `task_text`：用户粘贴文本或文档解析后的内容
- `task_source`：`paste | file`
- `task_filename`（可为空）、`created_at`、`updated_at`

### Requirement

- `id`、`project_id`、`title`、`required`：必交 / 建议
- `description`：完整要求文本
- `source_ref`：原文段落、MD 行、PDF 页或 DOCX 段落标识
- `constraints`：已确认的可验条件数组，例如 `[{type:"video_duration",min_seconds:300,max_seconds:480}]`
- `needs_manual_review`：是否包含必须人工复核的内容
- `confirmed`：草稿/已确认
- `review_decision`：`pending | pass | fail`，`review_note`
- `last_check_result`、`last_checked_at`（不另建历史表）

### Artifact

- `id`、`project_id`、`original_name`、`stored_path`、`mime_or_ext`、`bytes`、`uploaded_at`
- 上传后由系统保存独立内部路径。文件原名用于展示和导出；不作为版本相同的依据。

### RequirementArtifact（关联）

- `requirement_id`、`artifact_id`、`selected`（是否参与当前要求的提交检查）
- 同一要求可关联多文件，同一文件可关联多要求；数据库唯一约束阻止同一关联重复计数。

**不新增哈希**：替换行为必须经过应用 API，新上传生成新的 Artifact ID，更新关联并重置受影响的检查结果与人工复核。直接修改服务器上传目录中的文件不属于产品操作流程。

## 3. 验收计算口径

- 一个 Requirement 可以有多个 `constraints`（例如 MP4 格式 + 5–8 分钟 + 视频内容人工复核）。
- `selected` 决定用于检查的实际文件；单文件要求至多选定一份，多文件数量要求允许选定多份。
- 客观检查：`exists`、`extension`、`pdf_pages`、`video_duration`、`file_count`。阈值来自已确认的 Requirement。
- 内容类要求采用 `needs_manual_review`，用户可以明确填写人工结论。
- 综合状态：已确认要求缺必交证据或有明确失败 ⇒ 不通过；否则仍有待复核/检查异常 ⇒ 待复核；否则通过。
- 非必交建议项单独展示，不进入必交项总体通过数的判断。
- 替换/删除文件、取消关联、调整选定文件、修改约束时：使受影响 Requirement 的旧自动检查结果失效；证据集合改变时复核状态回到 pending。
- 检查异常不伪装成客观不合格；显示错误原因并保留待处理状态。

## 4. API 开发顺序

### 阶段 1（立即实现）

- `GET /api/health`：本地服务健康检查。
- `GET /api/projects`：列出项目。
- `POST /api/projects`：创建 `{name, kind}`。
- `GET /api/projects/{id}`：读取项目。
- `PATCH /api/projects/{id}`：修改名称/类型。
- `DELETE /api/projects/{id}`：删除项目。
- `PUT /api/projects/{id}/task`：保存 `{task_source:"paste", task_text:"..."}`。

阶段 1 不实现 AI、成果上传、验收或导出 API；前端为后续页面预留导航入口即可，不放假数据或假按钮。

### 阶段 2

- `POST /api/projects/{id}/task-file`：任务文件上传、文本提取、来源定位。
- `POST /api/projects/{id}/extract`：AI 提取要求。失败可手动录入。
- 要求的读取、创建、编辑、删除与确认 API。

### 阶段 3

- 成果上传、文件列表、删除、定向关联、从文件库选择、选定提交文件 API。
- 文件上传分块写入磁盘，避免整个视频文件进入内存。按 PRD 中每类限制检查大小。

### 阶段 4

- 已确认规则的客观检查、人工复核、状态刷新 API。
- 缺失、文件变更、规则修改引起的结果失效。

### 阶段 5

- 最终文件选择、报告生成、ZIP 导出 API。
- 真实案例验证、UI 打磨、参赛材料。

## 5. 项目目录建议

```text
submitlens/
├── frontend/             # React + TS + Vite
│   └── src/
├── backend/              # FastAPI
│   └── app/
├── docs/
│   ├── PRD.md
│   ├── UI_COPY.md
│   ├── ENGINEERING.md
│   └── ACCEPTANCE.md
├── data/                 # SQLite + 上传文件，本地生成且不入 Git
├── .env.example          # 可读配置模板，无真实密钥
├── .gitignore
└── README.md             # 10 分钟复现入口
```

不要为了与目录完全一致而迁移已有代码；如果仓库已有合理目录，优先沿用。

## 6. 阶段排期（以 11 月 18 日提交为界）

| 阶段 | 日期 | 验收产物 |
|---|---|---|
| 1. 项目与文本输入 | 11/05–11/06 | 真实 Web UI + 项目存储 + 粘贴说明，刷新不丢失 |
| 2. 文件解析、要求提取 | 11/07–11/08 | 可编辑/确认要求，原文依据，手工降级 |
| 3. 成果上传与关联 | 11/09–11/10 | 批量/定向上传，持久化关联，选定提交文件 |
| 4. 检查与重检 | 11/11–11/12 | 客观检查、人工复核、修改后状态更新 |
| 5. 导出、两个案例 | 11/13–11/14 | ZIP + 报告，竞赛/课程均走通 |
| 6. 精修与交付 | 11/15–11/17 | UI、README、录屏、Prompt 记录、技术文档 |
| 截止提交 | 11/18 | 不安排新功能 |

## 7. AI 协作开发与复现记录

- 每个核心模块完成后提交一次真实 Git commit，提交信息对应真实改动；不要将整个项目压成一次 initial commit。
- 至少留存三段完整的 AI 协作记录：**要求提取**、**文件关联/失效**、**自动检查与导出**。保留用户指令、模型修改建议和真实 Bug 修复往返。
- README 含 Python/Node 版本、依赖安装、本地启动、`.env.example`、无 Key 手动流程和两份案例使用步骤。
- 技术文档及视频介绍真实交付流程与 AI 如何协作开发，而非展示虚构的开发过程。

## 8. 先不引入的东西

通用事件总线、抽象仓储层、规则 DSL、队列、向量库、完整版本系统、文件 hash、运行任意代码的沙箱、模拟的云服务及未被真实失败驱动的额外校验机制。
