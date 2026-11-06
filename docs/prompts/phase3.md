# 阶段三协作与修复过程

日期：2026-11-06。用户完整阶段三指令、可见答复与授权记录见 phase3-conversation.md；本文件保留实际工具执行与修复，不代替原始对话。起点 origin/main 517014e，fetch/ff-only 结果 Already up to date。保留用户新增的 test/ 忽略项。

## 功能增量

1. a859476：修复旧原文要求直接重新确认及 AI 重复草稿；在原有 JSON 中增加 stale/origin，不引入版本系统。旧原文要求整单确认跳过，人工核对编辑后恢复。来源未知的历史条目按受保护条目处理，不冒充可替换 AI 草稿。
2. 9bd8e8e：artifacts 与 requirement_artifacts 两表，内部 UUID 落盘、分块上传、同名隔离、删除清理、项目限定、多对多去重、单件/数量选择；配套集成检查。
3. 1a29cf1：成果覆盖工作台、定向/批量上传、已有库复用、双向跳转、选择与解绑、替换和进度；正式要求与草稿分开，交付中心不启用。
4. 收尾：曾确认要求在原文变更后也受保护；再次关联不清除选定；按扩展名和 MIME 分类上限；完善断言、README 和真实验收。

## 实际修复往返

- 初始重复提取每次成功插入要求。改为只有显式 replace_ai_drafts=true 才能替换未确认且未编辑 AI 草稿；新生成仍是草稿。模型失败时不删除旧数据。
- 原文修改只取消 confirmed，后续 confirm 全部恢复。现在 unconfirm 同时标 stale，confirm 跳过，界面明确“原文已变，需处理”。人工编辑保存才清理 stale。
- 检查确认/失效路径后发现：曾确认的 AI 条目因原文更新变成未确认，仍可能被替换。确认后使用现有 origin=reviewed 保护，新增对应断言。
- 初版关联 PUT 默认 selected=false，用户再次从库选择可能清除最终选择。调整为 {} 仅去重关联，不更改 selected；显式布尔才更改选择。
- 成果页每次上传先写新 UUID 文件，全部写完才入库。单批超限或读取中断回滚文件与关联；替换新 ID，关联保留但选定取消。未引入文件哈希。
- 首次浏览器命令误加 Playwright 不支持的 --test-dir 选项，失败后从 frontend 目录执行 npx playwright test --reporter=line，最终 4 passed。
- 本机上次后端进程仍在 8000；核对 uvicorn 命令后重启为阶段三代码，未停止无关服务。
- 查看真实模型响应时终端 GBK 无法输出 • 字符，仅读取输出失败；后续明确 UTF-8 后完成核对，没有重新调用模型。

## 真实模型与审批

首次调用命令在执行前被自动审批拒绝，理由为外发目的地与完整 payload 授权不够明确；未绕过。随后请求用户确认官方 DeepSeek 接口、完整赛道文本、请求头密钥与费用，用户答复“授权这次 DeepSeek 提取”，才执行一次真实请求。模型返回内容，但不存在的组合 ref 导致应用 502、拒绝入库。原始本地证据路径与人工核对见 ../phase3-acceptance.md。不以替身成功冒充真实提取成功。

## 最终检查

- .venv/Scripts/python backend/check_phase1.py：退出码 0。
- .venv/Scripts/python -m backend.check_phase2：2 tests OK。
- .venv/Scripts/python -m backend.check_phase3：2 tests OK；实际子进程重启、文件隔离、多对多、选择、替换、删除、超限/中断清理、任务原文与要求清单不变。
- frontend 下 npm run typecheck / npm run build：退出码 0，30 modules。
- frontend 下 APP_URL=http://127.0.0.1:5174 的 npx playwright test --reporter=line：4 passed，5.1s，已查看桌面及 375px 截图。
- 真实 test 内三种文件本地上传均 201，包括 61,718,568 B 的 MP4，删除测试项目后磁盘文件 0。
- 未上传真实 1 GB 边界文件；超限与清理用小上限替身覆盖写入失败分支。未实现任何检查/人工复核结论。

## 开源边界

查阅 JanusTrace README 的覆盖/追踪呈现和 DeepSeek 官方接口文档；未复制第三方源码，没有新增 JanusTrace/langextract/markitdown/checklist 依赖。JanusTrace 只参考信息架构，来源 https://github.com/yesilzeytin/JanusTrace；接口配置来源 https://api-docs.deepseek.com/。未改换现有文档解析库。

没有追踪 test/、data/ 或 .env。未推送远程；当前停止阶段三，实际验收与导出属于后续工作。
