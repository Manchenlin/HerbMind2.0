# docx 正文补录操作手册（R2）

> 本文记录 2026-11-11 那次「把 docx 里没进库的正文补进 `content_unit`」的完整操作、数据变化、踩过的坑与复现步骤。
> 所有数字都是当天在本机库里 **实测** 出来的，不是估算。换机器重做时，按第 3 节照抄命令即可。
>
> 相关代码：`database/etl/import_docx_gap.py`（新增）、`scripts/smoke.py`（基线更新）、
> `backend/svc-catalog/.../BookMapper.java`（补录单元排序）。

---

## 0. 一页速查

| 项 | 值 |
|---|---|
| 要解决的问题 | 原书 9.7% 的正文（672 段 / 38,875 字）从未入库 |
| 源文件 | `D:\HomeWork\_KeYanShiJian\中医经典方证原文.docx`（**注意目录名是 `_KeYanShiJian`，不是仓库的 `_KeYanShJian`**） |
| 脚本 | `database/etl/import_docx_gap.py` |
| 写入前缀 | `cu_gap_`（只删自己的行，不碰存量） |
| 数据变化 | `content_unit` 538 → **598**；`section_abstract` 58 条、`table` 2 条 |
| 一句话执行 | `python database/etl/import_docx_gap.py --apply` |
| 一句话回滚 | `DELETE FROM content_unit WHERE id LIKE 'cu_gap_%';` |

---

## 1. 背景：为什么要补

### 1.1 根因

旧链路是 `docx → 旧库 rag_chunk → migrate_legacy.py → content_unit`。`rag_chunk` 的切块**以 `【问题】` 为锚点**：
一段「问题 → 解答」切成一个块。锚点之外的内容——节首概述、病机论述、治则转归、医案里的辨证按语——在切块时被直接丢掉。

所以这不是解析 bug，也不是迁移 bug，**是切分策略的固有损失**，且旧库实例（5433）已不在运行，无法回溯修切分再重迁。

### 1.2 数据对照（实测）

| 指标 | 补录前 | 补录后 |
|---|---|---|
| docx 原始段落 | 8,788 | — |
| docx 清洗后段落 | 7,939 | — |
| docx 正文字数（去空白、不含表格占位） | 400,899 | — |
| 库内单元数 | 538 | **598** |
| 库内正文字数（去空白） | 377,934 | 416,809 |
| 未入库真叙述 | 672 段 / 38,875 字（9.7%） | 2 段 / 32 字 |

补录后按 `unit_type` 的分布（验收基线）：

| unit_type | 条数 | 字符数 |
|---|---|---|
| `full` | 535 | 366,908 |
| `section_abstract` | **58** | 39,550 |
| `theory` | 3 | 18,825 |
| `table` | **2** | 472 |
| 合计 | **598** | — |

补录在 `cu_gap_%` 下共 60 条 / 40,022 字符（含换行），按章分布：

| 章 | 补录条数 | 字符数 |
|---|---|---|
| 第三章《温病学》方证案例研究 | 27 | 25,636 |
| 第二章《伤寒论》方证案例研究 | 10 | 7,638 |
| 第四章《金匮要略》方证案例研究 | 23 | 6,748 |
| 第一章 经典·证治·案例 | 0 | 0 |

缺口最重的几节：春温病证治 4,992 字、风温病证治 4,357 字、湿温病证治 3,878 字、伏暑证治 3,565 字、太阳病方证案例 2,640 字。

---

## 2. 前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| PostgreSQL | 容器 `herbmind-v2-pg` 运行中，`localhost:5432`，库 `herbmind`，账号 `postgres/postgres` | `docker ps --filter name=herbmind-v2-pg` |
| Python | conda 环境 `herbmind`（3.11.17） | `"D:\software\anaconda\anaconda_1\envs\herbmind\python.exe" -V` |
| 依赖 | `psycopg2`、`python-docx` 已装在该环境 | `python -c "import psycopg2, docx; print('ok')"` |
| 源 docx | 路径存在（1.24 MB） | `dir "D:\HomeWork\_KeYanShiJian\中医经典方证原文.docx"` |
| Embedding | `agent/.env` 里有 `LLM_API_KEY`（硅基流动 `BAAI/bge-m3`，1024 维） | 脚本启动时会打印 `embedding：BAAI/bge-m3（1024 维）@ ...` |

`--check` / `--dry-run` **不调 API、不写库**，可以在没有 key 的机器上跑。只有 `--apply` 需要。

---

## 3. 复现步骤

> 所有命令都在仓库根目录执行；PowerShell 下调 exe 要用 `& '完整路径'`，见坑 12。

### 3.1 步骤 1：缺口统计（默认行为，只读）

```powershell
& 'D:\software\anaconda\anaconda_1\envs\herbmind\python.exe' database/etl/import_docx_gap.py --check
```

**在「没补过」的库上，输出必须是这样**（数字对得上才继续）：

```
=== 缺口统计 ===
清洗后段落 7939，章/节标题 46 个
未入库的正文段落 672 段、38875 字
排除项：目录页 9、纯标记行 706、标题行 43、表格占位 78、页眉噪声 2、无归属节点 0
计划生成 60 个补充单元（39341 字），涉及 36 个节点

=== 按节点分布（前 10）===
  4992 字 / 1 单元  第十一节 春温病证治
  ...
```

如果 `未入库的正文段落` 明显不是 672，先别写库，按坑 10 / 坑 11 排查源文件与节点。

### 3.2 步骤 2：干跑看样例

```powershell
& 'D:\software\anaconda\anaconda_1\envs\herbmind\python.exe' database/etl/import_docx_gap.py --dry-run
```

会额外打印前 3 个单元的正文，以及 2 个表格单元。人工确认两件事：

1. 单元正文是**原书原文原样**，没有被改写、没有被拼错顺序；
2. `page=第19-22页` 这类页码与该节在原书的位置对得上（第 19 页应该是第二章太阳病，不是第 304 页——若出现 304 说明踩了坑 2）。

### 3.3 步骤 3：写入

```powershell
& 'D:\software\anaconda\anaconda_1\envs\herbmind\python.exe' database/etl/import_docx_gap.py --apply
```

输出应包含：

```
embedding：BAAI/bge-m3（1024 维）@ https://api.siliconflow.cn/v1
  已取向量 16/60
  ...
已删除旧补录行 0 条，写入 60 条
下一步：python build_graph.py（把新单元同步进 Neo4j）
```

- 第一次跑「已删除旧补录行 **0** 条」；重跑时会显示 60，这是正常的幂等行为。
- 只调 60 次 embedding，成本可忽略（每条约 600 字）。

### 3.4 步骤 4：验收

**A. 结构验收（SQL）**

```bash
docker exec herbmind-v2-pg psql -U postgres -d herbmind \
  -c "SELECT unit_type, count(*), sum(length(content)) FROM content_unit GROUP BY 1 ORDER BY 2 DESC;" \
  -c "SELECT count(*) FROM content_unit WHERE id LIKE 'cu_gap_%';" \
  -c "SELECT count(*) FROM content_unit c WHERE c.id LIKE 'cu_gap_%' AND NOT EXISTS (SELECT 1 FROM book_node n WHERE n.id = c.ref_id);" \
  -c "SELECT count(*) FILTER (WHERE embedding IS NOT NULL) AS 有向量, count(*) AS 总数 FROM content_unit;"
```

期望：

| 查询 | 期望值 |
|---|---|
| `unit_type` 分布 | full 535 / section_abstract 58 / theory 3 / table 2 |
| `cu_gap_%` 条数 | 60 |
| 挂空节点的补录单元 | **0**（非 0 说明 `book_node` 被重建过，要按坑 11 重跑） |
| 向量 | 598 / 598 |

**B. 接口验收（补录是否真的出现在阅读页）**

```bash
curl -s -o nul -w "n_s1  %{http_code}  %{size_download}B\n" "http://localhost:8082/internal/catalog/node/n_s1/content"
curl -s -o nul -w "n_s15 %{http_code}  %{size_download}B\n" "http://localhost:8082/internal/catalog/node/n_s15/content"
```

期望：

- `n_s1`：**40 个单元**（原 37 + 3 条补录），第一条是 `refType=node` 的「概述」，`page=第19-22页`；
- `n_s15`：`200`、约 28 KB（补录前这里直接 **500**，见坑 1）。

**C. 排序验收**（补录单元要排在节首，不是节尾）

```bash
curl -s "http://localhost:8090/api/biz/catalog/node/n_s1/content" | python -c "import json,sys; d=json.load(sys.stdin)['data']; [print(i, x['refType'], x['page'], x['content'][:24].replace(chr(10),' ')) for i,x in enumerate(d['units'][:4])]"
```

期望前几条是 `node / 第19-22页 / 概述…`，然后才是方剂、医案。若补录单元排在最后，说明后端还是旧 jar——见坑 9。

**D. 冒烟**

```bash
cd scripts && python smoke.py
```

期望 11 项全 `PASS`，末尾 `SMOKE OK`：

```
PASS PG: content_unit=598  got 598
PASS PG: 向量覆盖全部单元  got 598/598
PASS PG: 向量 1024 维  got 1024
PASS Neo4j: Formula=245  got 245
PASS Neo4j: COMPOSED_OF>900  got 1288
```

### 3.5 步骤 5：图谱同步

```bash
cd database/etl && python build_graph.py
```

说明：`build_graph.py` **只同步 `formula` / `formula_herb`**，不处理 `content_unit`，所以补录本身不改变图。
但补录单元行的 `graph_synced` 是 `false`，如果以后治理流按这个字段统计同步率，需要知道它们本来就不该进图（节级概述不是方剂/医案）。

### 3.6 全量重建 / 换机器 / 部署的顺序

**顺序不能换**，`migrate_legacy.py` 会 `TRUNCATE`，先跑它会把补录冲掉：

```
1. migrate_legacy.py                       # 从旧库 rag_chunk 迁 content_unit（会清表）
2. apply_supplement.py                     # 补 formula_herb 309 条组成
3. sync_content_unit.py                    # 重算全部向量
4. merge_book_and_import_chapter1.py       # 三本书合一 + 补回第一章（会重建 book_node）
5. import_docx_gap.py --apply              # 本手册的补录，按节点标题挂接
6. build_graph.py                          # 方剂图谱
```

第 4 步必须在第 5 步之前：`import_docx_gap.py` 是按 `book_node.title` 匹配节点的，节点被重建后必须重跑第 5 步，否则补录会挂到不存在的节点上（验收 SQL 里"挂空节点"会大于 0）。

---

## 4. 脚本怎么工作

### 4.1 判定「哪些段落是缺口」

逐段过 docx（清洗后的 7,939 段），先判断是否已入库，再判断是否属于该补的正文：

| 判定 | 规则 | 实测命中 |
|---|---|---|
| 已入库 | 该段去掉空白后在**本节语料**里能找到（本节没有语料时退回全库语料） | 7,267 段 |
| 目录页 | 长度 > 200 且（含 ≥3 个 `…` 或 ≥3 个 `(数字`），或整段是「目录」 | 9 |
| 纯标记行 | 整段只有一个 `【xxx】`（如 `【原文回顾】`、`【案例】`） | 706 |
| 标题行 | 长度 ≤ 40 且以 `第X章` / `第X节` 开头 | 43 |
| 表格占位 | 等于 `[表格]` | 78 |
| 页眉噪声 | 含「案例研究」且去空白后 ≤ 25 字（`甲乙经典方证案例研究`、`第二早《伤寒论》力证案例研究`） | 2 |
| **补录正文** | 以上都不是 | **672** |

### 4.2 归属节点

按 docx 顺序跟踪"最近的章标题 / 节标题"，用 `fix_ocr` 纠错后与 `book_node.title` 匹配：

1. 精确匹配（去空白后相等）；
2. 模糊匹配（`difflib` ratio ≥ 0.72）；
3. 节匹配失败时退回父章节点（例如「第一节 脏腑经络先后病脉证」这一节在 `book_node` 里根本不存在，见坑 11）。

实测 46 个章/节标题里 44 个精确命中，1 个是重复的极简「第一章」（跳过），1 个是上述缺节。

### 4.3 页码：为什么必须「按节」定位

每个补录单元写 `meta_jsonb.page`，值取「该单元首段之前、**同一节内**最近一个已入库段落的页码」。

不能在全库正文里找，原因见坑 2。落到数据上：`太阳病`的概述落在 `第19-22页`，「太阳变证」落在 `第37-38页`，与原书一致。

找不到参照时（该节一条都没入库）退化顺序：该节最小页码 → 目录表格里解析出的节起始页 → 空（空则该单元排到节末）。

实测只有 1 个单元拿不到页码（挂在章节点上的「第一节 脏腑经络先后病脉证」）。

### 4.4 单元切分与 id

- 按节点分组，组内按原书顺序累积，单条超 **1,200 字**就断一条；
- id：`cu_gap_<节点id>_<序号三位>`，例如 `cu_gap_n_s1_001`；表格用 `cu_gap_<节点id>_t01`；
- `unit_type`：正文 `section_abstract`，表格 `table`；
- `ref_type='node'`、`ref_id` = 所属节节点 id；
- `meta_jsonb`：`{chapter, section, page, gap: true, gapSeq, source: "docx_gap"}`。

`gap: true` + `gapSeq` 是给后端排序用的，见坑 14。

### 4.5 幂等

`--apply` 先 `DELETE FROM content_unit WHERE id LIKE 'cu_gap_%'` 再整体插入，一个事务。
库存量 538 条从不参与写入，回滚只需一条 `DELETE`。

**注意**：脚本在判断"是否已入库"时**故意把自己的 `cu_gap_%` 排除在语料之外**，
所以补录完成后重跑 `--check` 仍然显示「672 段、38875 字」——这是设计，不是补录失败（见坑 13）。

### 4.6 表格

78 个表格里只有 2 个是真表格，其余 76 个是文档开头的目录点线页（1 行 3 列「标题……（页码）」）。

判定：整表拼接后含 `…` 且长度 > 200，视为目录页跳过；行数 < 2 也跳过。

转换规则（`table_to_text`）：

- 列数 ≥ 4 → 行式（首行是表头、首列是方名）：`麻黄汤——证候：…；病机：…；治则：…`
- 列数 = 3 且首行含「比较」→ 对比式：`相同点：A——…；B——…`

产出：

| 单元 id | 所属节 | page | 内容 |
|---|---|---|---|
| `cu_gap_n_s27_t01` | 第十四节 水气病脉证并治 | 第339-339页 | 桂枝去芍加麻辛附子汤 / 枳术汤（相同点·兼证·病机·治则） |
| `cu_gap_n_s30_t02` | 第十七节 呕吐哕下利病脉证治 | 第361-361页 | 生姜半夏汤 / 小半夏汤 / 半夏干姜散（证候·病机·治则·用药特点） |

---

## 5. 踩坑记录

> 每条格式：**现象 → 证据 → 根因 → 修法 → 怎么复现/怎么确认**。

### 坑 1：`/content` 接口对整片节点返回 500

- **现象**：第四章大部分节打开就报错，接口 500。第一章那几节正常。
- **证据**：
  ```
  {"code":5000,"msg":"... invalid byte sequence for encoding \"UTF8\": 0x00 ... (unnamed portal parameter $1)"}
  ```
- **根因**：`CatalogService` 里空集合哨兵写的是 `"\u0000none"`（想用 NUL 保证不冲突）。PostgreSQL 的 `text` 不接受 NUL 字节，参数里带 `0x00` 直接报错。而"本节没有方剂/医案挂接"的节点正好会走到哨兵——第四章多数节都是这样。
- **修法**：哨兵改成普通字符串 `"__hm_none__"`（`CatalogService.SENTINEL`）。
- **复现**：`curl -i "http://localhost:8082/internal/catalog/node/n_s15/content"`，修复前 500，修复后 200 / 28 KB。

### 坑 2：页码反查串到别的章节

- **现象**：第一版脚本把第二章太阳病的概述定位到了 `第304-306页`（那是第四章的页码）。
- **证据**：`--dry-run` 打印 `[cu_gap_n_s1_001] page=第304-306页`。
- **根因**：用「全库正文拼成一个串，`str.find` 找段落位置，取该位置的单元页码」。但全库正文是**按 id 顺序拼的**，不是按原书页序；同一句话在别的章节也出现过时，`find` 命中第一次出现的位置，页码就是别人的。
- **修法**：改成**按节建独立语料**（`load_section_texts`，key 是去空白后的节名），只在节内找位置。节内找不到就当缺口，不做跨节兜底。
- **确认**：`--dry-run` 里第二章的单元必须是 `第19-22页`（概述）、`第37-38页`（太阳变证）这类，出现 300+ 的页码就是没修好。

### 坑 3：页眉把「当前节」冲掉，表格被判成"只属于章"

- **现象**：2 个真表格提示 `[跳过表格] 无法定位节点：第四章《金匮要略》方证案例研究`，本该挂到节上。
- **根因**：docx 每页页眉都印一次章标题。表格提取函数里遇到章标题就执行 `chapter, sec = ft, ""`，把当前节清空；而表格恰好紧跟在页眉后面。
- **修法**：章标题**只在变化时**才重置节（`if ft != chapter: chapter, sec = ft, ""`）。
- **确认**：`--check` 的「真表格单元」段必须打印出 `cu_gap_n_s27_t01` / `cu_gap_n_s30_t02`。

### 坑 4：78 个"表格"里 76 个不是表格

- **现象**：按"78 个表格待结构化"排期，实际只有一个能算真表格的量。
- **证据**：逐表打印后发现 76 个是 1 行 3 列的「标题……（页码）」，全部集中在文档开头 body 位置 8–169，是**目录页被 Word 排成了表格**。
- **修法**：判据 `含 '…' 且长度 > 200` 直接跳过；只处理 2 个。
- **复现**：`extract_real_tables()` 打印每张表的行数/列数与首行即可看到。

### 坑 5：`smoke.py` 硬编码 535，补录后必然失败

- **现象**：补录后 `smoke.py` 报 `FAIL PG: content_unit=535 got 598`、`FAIL PG: 向量 535 条`。
- **根因**：基线写死在 `EXPECT` 与外层 `check("PG: 向量 535 条", with_vec == 535)` 里。
- **修法**：`content_unit` 基线 → 598 并注释说明来源；向量检查改成动态的"覆盖全部单元"（`with_vec == total`），以后再加单元不用再改脚本。
- **注意**：`feat/book-merge-and-chapter1` 分支同时把它改成过 538，两条分支合并时这里**必然冲突**，正确解法是取 598 + 动态检查。

### 坑 6：`mvn package` 说成功，fat jar 里还是旧依赖

- **现象**：改了 `contract` 模块的类，`svc-catalog` 启动报 `NoClassDefFoundError: com/herbmind/contract/catalog/NodeContentVO`，但 maven 明明 `BUILD SUCCESS`，jar 时间戳也更新了。
- **证据**：把 fat jar 里的 `BOOT-INF/lib/herbmind-contract-*.jar` 解出来比对——内嵌的是 106,934 字节的旧包，本地仓库里的是 109,117 字节的新包（含新类）。
- **根因**：`-pl svc-catalog`（不带 `-am`）时，`contract` 从本地仓库取；而本地仓库里的快照是旧的。加上之前有 java 进程锁着 jar，`repackage` 实际没写进去却报成功。
- **修法**：
  1. 先 `mvn -pl herbmind-contract install -DskipTests` 把最新 contract 装进本地仓库；
  2. 再 `mvn -pl svc-catalog **clean** package -DskipTests`（`clean` 必须加）；
  3. 验证 `BOOT-INF/lib` 里内嵌包的大小与本地仓库一致。
- **确认**：`java -jar` 启动日志里不再出现 `NoClassDefFoundError`。

### 坑 7：本地仓库不是 `~/.m2`

- **现象**：`mvn install` 说成功，但 `C:\Users\w1590\.m2\repository\com\herbmind\` 下找不到 `2.0.0-SNAPSHOT`。
- **证据**：`mvn help:evaluate -Dexpression=settings.localRepository` → `D:\software\IDEA\IntelliJ IDEA 2025.3.3\mvn_repo`。
- **影响**：排查依赖问题时会去错目录。
- **记法**：本项目所有 maven 产物都在 IDEA 的 `mvn_repo`，不是 `~/.m2`。

### 坑 8：改了 Mapper 的 SQL，接口没变化

- **现象**：`BookMapper.unitsOfNode` 加了排序规则，接口顺序没变。
- **根因**：SQL 写在 Java 注解里，编译进 jar；服务还是旧进程。
- **修法**：`clean package` → 停掉 8082 → 用新 jar 重启：
  ```powershell
  Start-Process -FilePath 'D:\Program Files\Java\jdk-21.0.11\bin\java.exe' `
    -ArgumentList '-jar','D:\HomeWork\_KeYanShJian\HerbMind\backend\svc-catalog\target\svc-catalog-2.0.0-SNAPSHOT.jar','--server.port=8082' `
    -WorkingDirectory 'D:\HomeWork\_KeYanShJian\HerbMind\backend' `
    -RedirectStandardOutput 'D:\HomeWork\_KeYanShJian\HerbMind\backend\svc-catalog.log' `
    -RedirectStandardError 'D:\HomeWork\_KeYanShJian\HerbMind\backend\svc-catalog.err.log' -WindowStyle Hidden
  ```
  日志在 `backend/svc-catalog.log` / `.err.log`（已被 `*.log` 忽略）。

### 坑 9：补录单元排到了节尾

- **现象**：新单元 `page` 正确，但显示在该节最后。
- **根因**：`unitsOfNode` 的排序是 `coalesce(page, 999999), u.id`；同页并列时按 id 字符串比，`cu_gap_...` 的 `g` 大于数字，永远排后面。
- **修法**：排序加一级（只影响同页）：
  ```sql
  CASE WHEN u.meta_jsonb->>'gap' = 'true' THEN 0 ELSE 1 END,
  coalesce(nullif(u.meta_jsonb->>'gapSeq','')::int, 0)
  ```
- **确认**：`n_s1` 的前几条应该是 `node / 第19-22页`，不是方剂。

### 坑 10：docx 路径的目录名有两个相似版本

- **现象**：脚本报「源 docx 不存在」。
- **根因**：机器上有 `D:\HomeWork\_KeYanSh**i**Jian\`（源资料）与 `D:\HomeWork\_KeYanShJian\`（本仓库）两个目录，只差一个字母位置。
- **记法**：源文件在 `_KeYanShiJian`（Shi），仓库在 `_KeYanShJian`（ShJ）。

### 坑 11：「第一节 脏腑经络先后病脉证」在 `book_node` 里不存在

- **现象**：`--check` 报告 1 个标题未匹配；该节内容被挂到父章节点上。
- **证据**：`book_node` 里第四章（`n_h3`）下的节从「第二节 痉湿暍」开始，缺第一节。
- **影响**：该节补录单元的 `ref_id` 是章节点 `n_h3`，`title` 仍是节名，能读到但不在正确层级。
- **修法（未做）**：在 `book_node` 补一行第一节节点后可重跑 `import_docx_gap.py --apply` 自动归位。
- **连带**：如果以后有人重建 `book_node`（如 `merge_book_and_import_chapter1.py`），**必须重跑本补录**，用第 3.4 节「挂空节点」那条 SQL 验收（必须为 0）。

### 坑 12：PowerShell 环境下的命令写法

本项目在这台机器上用 PowerShell 执行命令，几个地方会踩：

| 写法 | 结果 | 正确写法 |
|---|---|---|
| `cd /d D:\path; cmd` | `Set-Location: 找不到接受实际参数“D:\path”` | `Set-Location 'D:\path'` |
| `git -C D:\path add ...` | `error: unknown switch 'C'` | `Set-Location 'D:\path'; git add ...` |
| `"D:\...\python.exe" x.py` | 解析错误 | `& 'D:\...\python.exe' x.py` |
| `cmd1 & cmd2` | 语法错误 | `cmd1; cmd2` |
| `git ... 2>&1 \| Select-String` | 把 git 的正常 stderr 当异常显示 | 正常，忽略 `NativeCommandError` 即可 |

### 坑 13：补录完成后重跑 `--check` 仍显示 672 段缺口

- **现象**：`--apply` 成功、库里 60 条都在，但再跑 `--check` 还是「未入库的正文段落 672 段」。
- **根因**：脚本判断"已入库"时**排除 `cu_gap_%`**，否则重跑会把补录内容当成存量、计划变成空表，幂等就废了。
- **正确验收方式**：看库里 `count(*) WHERE id LIKE 'cu_gap_%'`（应为 60）与 3.4 节的 SQL，不要看 `--check` 的缺口数。

### 坑 14：`meta_jsonb.gap` 这个标记是排序契约

- **说明**：补录单元写 `gap: true` / `gapSeq`，后端 `BookMapper.unitsOfNode` 依赖它把补录排到同页原文之前。
- **影响**：谁要是重写这段 SQL 而漏了这两个 key，补录会全部掉到节尾（不会报错，只会顺序怪）。
- **记法**：改 `unitsOfNode` 的 `ORDER BY` 时，保留 `gap` / `gapSeq` 那一级。

---

## 6. 回滚

```sql
-- 只回滚本轮补录，存量 538 条不受影响
DELETE FROM content_unit WHERE id LIKE 'cu_gap_%';
```

回滚后：

- 单元总数回到 538；
- `smoke.py` 的 `content_unit=598` 会 FAIL，把 `EXPECT["content_unit"]` 改回 538、并把向量检查改回硬编码即可；
- 后端排序那一级保留无害（库里没有 `gap` 标记的行）。

如需连同代码一起回滚：`git revert` 对应提交（`ffdca74` 补录脚本 + `888e1f7` catalog 排序）。

---

## 7. 验收清单（复制粘贴用）

```
□ docker ps 里 herbmind-v2-pg 为 healthy
□ python database/etl/import_docx_gap.py --check   → 672 段 / 38875 字 / 60 单元
□ python database/etl/import_docx_gap.py --dry-run → 样例正文为原文、页码在 19-400 区间合理
□ python database/etl/import_docx_gap.py --apply   → 写入 60 条、向量 60/60
□ SQL unit_type 分布 = 535 / 58 / 3 / 2
□ SQL cu_gap_% = 60，挂空节点 = 0
□ SQL 向量 598/598，1024 维
□ 接口 n_s1 = 40 单元且首条是 node 类型
□ 接口 n_s15 = 200（不是 500）
□ python smoke.py → 11 项 PASS / SMOKE OK
□ 前端典籍页：第二章第一节能看到「概述」，第四章能看到 2 个方证比较表
```

---

## 8. 本次变更的文件

| 文件 | 变更 |
|---|---|
| `database/etl/import_docx_gap.py` | 新增，本手册主体脚本 |
| `scripts/smoke.py` | `content_unit` 基线 535 → 598；向量检查改为"覆盖全部单元" |
| `backend/svc-catalog/.../CatalogService.java` | 空集合哨兵 `"\u0000none"` → `"__hm_none__"`（坑 1） |
| `backend/svc-catalog/.../BookMapper.java` | `unitsOfNode` 排序增加 `gap` / `gapSeq`（坑 9） |

数据库侧变更（不可 version control，靠本手册复现）：

- `content_unit` +60 行（58 `section_abstract` + 2 `table`），全部带 1024 维向量；
- 存量 538 行**未改动一个字段**。
