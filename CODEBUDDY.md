# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

本仓库由三个域并行开发（域1 内容域 / 域2 成长域 / 域3 智能域）加前端，本文件是**所有参与者（人与其 AI 助手）共同遵守的行为规范**。

本文件只写"该怎么做"，不写"系统长什么样"。架构、端口拓扑、数据层、ETL 顺序、各服务实现约束、环境坑这类**技术细节一律不写在这里**——它们对具体某个人或某个模块的针对性太强，写进来会让每个人每次会话都灌一大段与己无关的内容。进度怎么记、技术细节去哪查，见文末第九节。

---

## 一、边界：只做自己的模块

- 三个域的代码、文档、数据脚本各归其负责人。**只在自己的模块里改代码**，未明确指派时不要碰别人的东西。
- 看到别人的代码有问题：写清"现象 / 证据 / 影响"交给负责人，**不要顺手修掉**。
- 跨域改动（公共契约、`herbmind-common`、网关路由、`database/pg` 的 DDL）先与受影响方确认，再动手。
- 分工与接口口径以 `project_plan/15_团队分工与接口协作.md`、`project_plan/09_API契约清单.md` 为准；若与 `project_plan/00_README_总览.md` 的设计红线冲突，以红线为最高优先。

## 二、分支纪律：先建分支，再动代码

- **改任何代码之前，先建分支**：`git switch -c feat/<主题>`（修复用 `fix/<主题>`，杂务用 `chore/<主题>`）。**不得在 `master` 上直接改文件**。
- **每次动手前先确认自己在哪条分支上**：`git branch --show-current`。输出是 `master` 就先停下来建分支，不要凭印象认为"刚才切过"。同理，切换过目录或换过终端后要重新确认。
- 一条分支只做一件事。不要把不相关的功能堆在同一分支上；分支名要能看出做什么。
- **任务收尾时主动检查有没有"已做完但没合并"的分支**（`git branch --no-merged master`），有就提醒用户合并，并说明"合并到哪条分支、影响哪些文件、有无冲突风险"。
- 合并、删除分支、`reset` 属于红线操作，仍需先问（见下节）。

## 三、红线操作：先问再做

以下操作**必须先得到明确同意**，不得以"顺手""反正已经写完了"为由跳过：

- `git commit`、`git push`、`git rebase`、`git reset --hard`、强制推送
- 合并分支、删除分支
- 删除文件、目录或 git 历史
- 修改 `.env`、密钥、token、证书、CI/CD 配置
- 任何对外发布或生产环境操作

## 四、接口与数据契约（跨域硬约定）

- **路由分层**：`/api/biz/**` 只给 BFF；`/api/agent/**` 只给 Agent；各 svc 只暴露 `/internal/**`，不进网关。
- **响应外壳**：`R<T> = {code, msg, data}`（`code=0` 为成功），分页 `PageResult<T> = {list,total,page,size}`。错误响应也必须套 `R`，不允许裸 `{"detail": ...}`。
- **命名**：JSON 用 camelCase，数据库列用 snake_case；时间 `TIMESTAMPTZ` ↔ `OffsetDateTime`（**禁用 `LocalDateTime`**）；ID 一律用字符串。
- `content_unit.search_tsv` 是 `GENERATED ALWAYS ... STORED` 生成列，**禁止被 ORM 映射**，否则写入报错。
- **建表只改 `database/pg/00→04`**（容器首次启动按序自动执行、全部幂等）；不要手改运行中的库结构。
- 数据快照（`*.sql` / `*.sql.gz`）、`target/`、`node_modules/`、`logs/`、`.env` 一律不入库。
- **向量空间是锁死的**（1024 维、`BAAI/bge-m3`）：换 embedding 模型等于把所有向量重算一遍，不是可调配置项。

## 五、设计红线（不可越界）

1. **只查证 + 引用，不推断功效、不推演证治**；禁止"该方功效为 X""此证宜用该方""两方合用可增效"。
2. **查不到就说查不到**；禁止"根据中医理论推测""一般来说""临床上多用于"这类无出处表述。
3. **不给处方建议、不给剂量建议、不生成新方**；涉及用药必须带"仅供学习参考，不构成处方建议"。
4. **能用规则算的不交给大模型**：组成比对、集合差集、Jaccard、频次统计一律确定性代码，LLM 只做语言组织与语义理解。
5. **文档、提示词、原型里的"方名↔组成"必须能在库里查到**，禁止凭印象写。

全文与依据（含反例）见 `project_plan/00_README_总览.md` 的「设计红线」章节。

## 六、代码风格

- 前端：Vue 3 + TS `strict`，**禁止 `any`**，不引入 Element Plus 之类 UI 库。
- UI 文案与代码注释**一律中文**；面向用户的提示要能指导下一步，不要只甩错误码。
- Java：Spring Boot 3 + MyBatis-Plus；Python：FastAPI + pydantic v2，公开函数写类型标注。

## 七、回答方式

- **结论先行**：第一句就给结论或答案，然后才是依据、证据、过程。不要用"让我先看看""分析一下"开场，也不要结尾再把结论重复一遍。
- **不做谄媚式表达**：禁用"你这个问题问得很好""这个想法太棒了""非常抱歉给您带来困扰"这类影响判断的套话；不自我评价"完美""优秀""彻底解决"；不夸大成果，不掩饰没做到的部分。有错直接说，做不到直接说。
- **只做客观分析**：给事实和权衡，让用户自己判断。不确定就明说"不确定"，**不要用印象补全**（这是设计红线五的延伸）。
- 提方案先列 **2-3 个选项**，用大白话说清各自的好处与坏处，给出推荐及理由，**等确认再动手**，不先做后说。
- 遇到术语先解释"是什么 / 干什么用 / 为什么选它"。

## 八、统一入口命令（所有人同一套，不要自创）

- **中间件**：`bash scripts/start-infra.sh`（只 `up -d` + 等 healthy，**永不 `down -v`**）
- **导数据**：`bash scripts/init-data.sh <快照路径> [--reset]`
- **后端**：`cd backend && mvn -q package -DskipTests`，随后 `bash scripts/run-dev.sh`
- **前端**：`cd frontend && npm install && npm run dev`（`npm run build` 兼作类型检查，项目无 ESLint）
- **Agent**：`cd agent && python run.py --reload`（**必须在该目录下启动**）
- **测试**：`cd agent && python -m pytest tests -q`（目前只有 Agent 有自动化测试）
- **冒烟**：`python scripts/smoke.py`（需中间件与后端三件套已起）

## 九、文档与记录规范

- **项目进度记在 `PROJECT_MEMORY.md`**（仓库根，已进 `.gitignore`，只存本机、不进仓库）。
- 该文件**不宜过长**，只保留三块：**① 最高优先级规则　② 快速事实卡（当前进度要能一眼看到）　③ 分册目录**。其它内容一律写进 `memory/` 文件夹下的主题分册。
- 分册按主题切（环境与数据 / 各服务实现 / 数据问题 / 进度与分支 / 红线与复盘 / 代码约定 / 拓扑与命令），索引里为每册登记一行"做什么 / 什么时候看"。
- 事实必须带 `[实核 日期]`；**推翻旧结论时保留旧值并标注"已过期"**，不要直接删，否则下次会踩回去。
- **技术细节不要写进本文件（`CODEBUDDY.md`）**：它每次会话对所有人全文注入，塞细节等于让每个人白占上下文。
- **要查技术细节**：`README.md`、`docs/新人上手指南.md`、`project_plan/`；本机的 `PROJECT_MEMORY.md` + `memory/` 分册是逐条实核过的事实（端口拓扑、ETL 依赖链、踩过的坑），优先级高于任何口头描述。
- 给组员看的是 `README.md` / `docs/` / `project_plan/`；`PROJECT_MEMORY.md` 与 `memory/` 是维护者本机的记录。

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（21 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.codebuddy/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能、修改行为，或筹划任何新东西，无论是软件还是软件之外（一场分享、一门生意、一次装修）。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **diagnosing-superpowers**: 当一次 superpowers 会话出了问题、你的人类伙伴想知道原因时使用——重复劳动、无视计划、磕磕绊绊、结果质量差、某个技能没触发、"太慢了"、"为什么这么贵"、"它到底在干什么"——或者想给 superpowers 维护者整理一份 bug 报告；适用于当前会话，或按 id / 路径指定的过往会话，任何工具均可
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你要在当前会话里亲自担任实现者执行一份实现计划时使用——你的人类伙伴选择了内联执行，或者没有可用的子智能体工具
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成这份工作时使用
- **mcp-builder**: 在构建 MCP 服务器或 MCP 工具时使用 —— 系统化的生产级 MCP 构建方法论，覆盖工具设计、错误处理、传输层选择与测试，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，读取对应的 `.codebuddy/skills/<skill-name>/SKILL.md` 并严格遵循其流程。
<!-- superpowers-zh:end -->
