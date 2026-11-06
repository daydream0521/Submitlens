# 阶段 2 协作与执行记录

日期：2026-11-06。用户要求基于 daydream0521/Submitlens 最新 main 开始，先修复浏览器历史导航丢失文本，再做文件解析、AI 要求提取、编辑确认与持久化，不进入成果上传、验收、导出。

## 输入约束

读取 docs/PRD.md、ENGINEERING.md、UI_COPY.md、ACCEPTANCE.md。用户明确要求四种文档、50 MB、可编辑原文与来源、兼容 Chat Completions、仅结构化要求、草稿确认、手工降级、换行与状态持久化。每条约束需引用原文；无 OCR、多 Agent、规则 DSL、队列或向量库。

## 模型决策与实现

1. git fetch origin main + git merge --ff-only origin/main：Already up to date，起点 9cc11ca。
2. 根据用户指出的 hashchange -> load 路径，监听器读取当前 dirty 状态；取消时恢复 URL、不读取覆盖原文。保留 beforeunload。独立提交 1cf6329。
3. 沿用 SQLite projects，迁移增加 task_segments；新增 requirements 表，内容存 JSON；不迁移项目结构。PDF 页、DOCX 段落/表格、MD 标题/行和文本段落保留来源；失败不写库。提交 4030ff3。
4. LLM 仅服务端配置，结构化响应通过 Pydantic 类型和原文子串匹配；模型返回任意内容不能自动 confirmed。调用失败保留原文与已有清单。实际 system prompt、输入构造和 JSON schema 完整保存在 backend/app/main.py 的 extract 中。
5. 要求列表按交付物标题显示，约束突出，详情折叠；手工 CRUD、草稿确认、事务拆分/合并；任务变化取消确认。提交 13caac9。
6. UI UX Pro Max 查询 error feedback forms --domain ux 返回表单错误定位、恢复操作、错误反馈。沿用 design-system/submitlens/MASTER.md，不重新生成设计体系。

## 实际失败与修复往返

- 8000 被之前的 uvicorn 占用。核对 PID 7764 的命令确属本项目后停止并用新虚拟环境重启。
- 最初浏览器连旧后端，来源字段格式不符导致页面未显示。换成最新服务后阶段 1 流程通过。
- 回归使用固定项目名，失败残留导致 strict mode 找到多个同名按钮；改唯一名称。
- 一次修改测试的脚本误从 frontend 下访问 frontend/tests，路径不存在；改根目录执行。
- 前进到相同 URL 不一定产生确认框，测试 once(dialog) 留在队列，之后出现重复 accept。改持久处理器按当前测试决策统一 accept/dismiss。
- 拆分/合并初稿是多个 API 写入，可能只完成部分；改为单数据库事务统一转换。该失败来自实际实现路径，无额外架构。

## 测试命令与最终结果

- 开发前 npm run typecheck 已执行；后续生产构建和类型检查成功（29 modules）。最初沙箱检查输出在持续进程中，未据此声称成功；最终授权执行退出码 0。
- .venv/Scripts/python backend/check_phase1.py：退出码 0，实际进程重启后持久化通过。
- .venv/Scripts/python -m backend.check_phase2：退出码 0，1 unittest，最终 0.575s。四格式、空 PDF/损坏路径、50 MB 超限、无 Key、断网、空与缺少引用响应、编辑确认、数据库重开、事务拆分合并。模型响应为测试替身，没有真实付费调用。
- npm run typecheck；npm run build：退出码 0。
- APP_URL=http://127.0.0.1:5174 的 npx playwright test --reporter=line：3 passed，4.9s。原有项目、历史导航保护、文件与手工要求确认刷新。
- 已查看 frontend/test-results/phase2.png 桌面实际渲染。测试截图与用户数据未纳入 Git。

## 记录范围与剩余验证

本文件保留关键输入、实现决定、实际修复与测试结果，代码与提交保留完整模型提示和变更；当前工具无法导出本聊天的逐条原始消息，因此它不是完整逐字聊天导出。完整原始协作对话仍在当前 Codex 聊天中，参赛逐字材料需从客户端导出。本次未伪造后续阶段的 Prompt 链。

没有仓库内完整赛道原文件，未做真实赛道/真实 LLM 人工端到端；测试文本来自用户列出的已知约束。不宣称推荐选题误提问题已在真实模型验证。无成果上传、验收、导出实现。未推送远程。
