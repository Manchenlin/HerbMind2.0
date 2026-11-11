# 《中医经典方证原文》全量导入 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把 `D:\HomeWork\_KeYanShJian\中医经典方证原文.docx` 的 4 章 / 38 节 / 约 228 个方证案例单元全量导入 PostgreSQL（book、book_node、case_record、case_section、classic_quote、content_unit），生成 bge-m3 向量，同步进 Neo4j，并让前端书架与目录树能真实浏览这本书。

**架构：** 新增一个一次性 ETL 脚本 `database/etl/import_case_book.py`，分三段执行：① 纯函数解析 docx → 中间 JSON；② 事务写入 PG（每表 `ON CONFLICT DO UPDATE`，单事务、失败整体回滚）；③ 复用 `sync_content_unit.py` 的 `embed_batch` 补向量。图数据库侧扩 `build_graph.py` 增 `:Book` / `:Case` 节点。前端只改两处硬编码（书单、首页书 chip）。

**技术栈：** Python 3.11（conda env `herbmind`，psycopg2、zipfile + xml.etree 解析 docx，不引入 python-docx）、PostgreSQL 15 + pg_jieba + pgvector、Neo4j 5、Vue 3 + TS strict、pytest / vitest。

**规格：** 本计划依据 `PROJECT_MEMORY.md`「导入一本新语料要动什么」实核结论 + 对 docx 的四轮结构扫描结果（`%TEMP%\docx_scan*.json`，见附录 A 的表结构事实）。

## 全局约束

- **只做数据导入，不改方剂库**：新书里的方剂**不新建** `formula` 行；方名能在 `formula.name` 精确命中才写 `case_record.main_formula_id`，命中不到写 NULL。
- 建表语句只改 `database/pg/00→04`，全部幂等；`case_record` 新增列用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`。
- ID 前缀沿用 `database/etl/db.py` 的约定：`bk_ / n_ / cs_ / sec_ / q_ / cu_`。
- 导入必须**单事务**，失败整体回滚；提供 `--dry-run` 只解析不写库。
- 时间字段一律 `TIMESTAMPTZ`，JSON 字段用 `jsonb`，中文文本不改写、不做"润色"。
- 前端文案与代码注释中文；TS strict，禁止 `any`。
- **不做人工逐条校对**，但必须做自动对账（数量、非空率、抽样打印 3 条）。
- 遇到疑似 OCR 错字，先查权威写法再改：书面依据 = 《伤寒论》《温病学》《金匮要略》通行本标题与方名，不凭印象替换。

## 审查重点（Review Focus）

1. **页眉页脚污染**：正文里混有 `第一章  经典·证治·案例`、`中医经典方证案例研究`、纯数字页码 —— 若未剔除，228 个单元里会混入大量伪段落，`content_unit.content` 直接脏掉。
2. **OCR 错字**：同一章标题存在 `方证案例研究 / 万证杂例研究 / 徬寒论` 三种写法，还有 `第四章《金匮要略》方证案例研究消失。` 这种批注混入 —— 不纠正会写进 `book_node.title`，前端目录树直接露错。
3. **单元边界错位**：以 `【问题】` 为锚点切单元，若漏掉"医案段在【问题】之前"这一点，会把现病史/治法切到上一个单元里。
4. **剂量被当组成**：`麻黄、桂枝各 18g` 是"两味药各 18g"，若按逗号硬切会把 `各 18g` 拆成独立药味。
5. **embedding 缺失**：`content_unit.embedding` 为 NULL 的行会被 `/ask` 主链的 `WHERE embedding IS NOT NULL` 全部过滤，导入看起来成功、问答却一问三不知。

---

## 任务 1：docx 清洗与文本块提取

**文件：**
- 创建：`database/etl/docx_reader.py`
- 测试：`test/test_docx_reader.py`

- [ ] **步骤 1：编写失败的测试**

```python
# test/test_docx_reader.py
from database.etl.docx_reader import clean_blocks, is_noise

def test_header_line_is_noise():
    assert is_noise("第一章  经典·证治·案例") is True
    assert is_noise("中医经典方证案例研究") is True
    assert is_noise("128") is True

def test_body_paragraph_is_kept():
    assert is_noise("现病史：全身皮肤无汗出23年。") is False

def test_clean_blocks_dedupes_repeated_headers():
    raw = ["第二章《伤寒论》方证案例研究", "第二章《伤寒论》方证案例研究", "【问题】"]
    assert clean_blocks(raw) == ["【问题】"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd test && python -m pytest test_docx_reader.py -v`
预期：FAIL，`ModuleNotFoundError: database.etl.docx_reader`

- [ ] **步骤 3：在 `database/etl/docx_reader.py` 实现**

签名固定为：`is_noise(text: str) -> bool`、`clean_blocks(raw: list[str]) -> list[str]`、`read_docx_blocks(path: str) -> list[str]`。

`is_noise` 判定三类：纯数字/页码符号、章节标题与书名的**重复出现**（第 2 次及以后）、已知页眉白名单（`中医经典方证案例研究`、四章标题的标准写法）。`read_docx_blocks` 用 `zipfile` + `xml.etree` 读 `word/document.xml`，按 `w:p` 顺序取 `w:t` 拼接文本，表格转成 `[表格]` 占位。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd test && python -m pytest test_docx_reader.py -v`
预期：3 passed
再对真实文件跑一次，确认清洗没有把正文吃掉：

```bash
python -c "from database.etl.docx_reader import read_docx_blocks, clean_blocks; b=clean_blocks(read_docx_blocks(r'D:\HomeWork\_KeYanShJian\中医经典方证原文.docx')); print(len(b))"
```

预期：输出在 **8000~9000** 之间（原始 8710 块，清洗只会变少不会变多）

- [ ] **步骤 5：Commit**

```bash
git add database/etl/docx_reader.py test/test_docx_reader.py
git commit -m "feat(etl): 新增 docx 文本块读取与页眉页脚清洗"
```

## 任务 2：错字纠正与章节骨架解析

**文件：**
- 创建：`database/etl/docx_outline.py`
- 测试：`test/test_docx_outline.py`

- [ ] **步骤 1：编写失败的测试**

```python
# test/test_docx_outline.py
from database.etl.docx_outline import fix_ocr, parse_outline

def test_ocr_typos_are_corrected():
    assert fix_ocr("第二章《徬寒论》方证案例研究") == "第二章《伤寒论》方证案例研究"
    assert fix_ocr("第二章《伤寒论》万证杂例研究") == "第二章《伤寒论》方证案例研究"
    assert fix_ocr("第四章《金匮要略》方证案例研究消失。") == "第四章《金匮要略》方证案例研究"

def test_outline_has_four_chapters():
    blocks = ["第一章  经典·证治·案例", "第一节   中医经典的作用",
              "第二章《伤寒论》方证案例研究", "第一节   太阳病方证案例",
              "第三章《温病学》方证案例研究", "第一节   风温病证治",
              "第四章《金匮要略》方证案例研究", "第一节   脏腑经络先后病脉证"]
    chapters = parse_outline(blocks)
    assert len(chapters) == 4
    assert chapters[1]["book"] == "伤寒论"
    assert chapters[1]["sections"][0]["title"] == "太阳病方证案例"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd test && python -m pytest test_docx_outline.py -v`
预期：FAIL，模块不存在

- [ ] **步骤 3：实现 `fix_ocr(text: str) -> str` 与 `parse_outline(blocks: list[str]) -> list[dict]`**

`fix_ocr` 用固定映射表（`徬寒论→伤寒论`、`万证杂例→方证案例`、`消失。→''`），映射表以注释形式标注依据。`parse_outline` 返回 `[{"title": str, "book": "伤寒论"|"温病学"|"金匮要略"|None, "sections": [{"title": str, "start_index": int}]}]`，`start_index` 是该节标题在清洗后 blocks 中的下标，供任务 3 切单元用。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd test && python -m pytest test_docx_outline.py -v`
预期：2 passed。另跑一次全量校验：`python -c "from database.etl.docx_outline import *; ..."` 打印章数（应为 4）与节数（应为 38），与附录 A 对账。

- [ ] **步骤 5：Commit**

```bash
git add database/etl/docx_outline.py test/test_docx_outline.py
git commit -m "feat(etl): 解析 docx 章节骨架并纠正 OCR 错字"
```

## 任务 3：案例单元切分与字段抽取

**文件：**
- 创建：`database/etl/case_parser.py`
- 测试：`test/test_case_parser.py`

- [ ] **步骤 1：编写失败的测试**

```python
# test/test_case_parser.py
from database.etl.case_parser import split_units, split_sections, parse_herbs

def test_unit_starts_before_question_marker():
    """医案段（现病史/治法）必须归到【问题】所在的那个单元，不能被切到上一个单元。"""
    blocks = ["现病史：无汗23年。", "治法：方拟麻黄汤。", "【问题】", "1.为什么？", "【问题解答】", "答：……",
              "现病史：头痛。", "治法：方拟桂枝汤。", "【问题】", "1.为何？", "【问题解答】", "答：……"]
    units = split_units(blocks)
    assert len(units) == 2
    assert units[0]["blocks"][0].startswith("现病史")
    assert "桂枝汤" not in "".join(units[0]["blocks"])

def test_sections_split_by_marker():
    unit = ["现病史：无汗。", "治法：方拟麻黄汤。", "【问题】", "1.为何？", "【论述】", "因为……"]
    secs = split_sections(unit)
    assert [s["kind"] for s in secs] == ["现病史", "治法", "问题", "论述"]

def test_combined_dose_is_not_split_into_extra_herb():
    """「麻黄、桂枝各 18g」= 两味药各 18g，不能解析出第三味药。"""
    herbs = parse_herbs("麻黄、桂枝各 18g，杏仁10g，甘草4g")
    assert herbs == [
        {"name": "麻黄", "dose": "18", "unit": "g"},
        {"name": "桂枝", "dose": "18", "unit": "g"},
        {"name": "杏仁", "dose": "10", "unit": "g"},
        {"name": "甘草", "dose": "4", "unit": "g"},
    ]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd test && python -m pytest test_case_parser.py -v`
预期：FAIL，模块不存在

- [ ] **步骤 3：实现三个函数**

`split_units(blocks) -> list[dict]`：单元边界 = 上一个单元结束 → 本单元 `【问题解答】` 结束；单元起点回溯到"上一个单元结束 + 1"（这样【问题】前的医案段天然落入本单元）。返回 `[{"index": int, "blocks": list[str], "title_guess": str}]`，`title_guess` 取单元内第一个 ≤20 字且不含"："的段落，取不到就用"案例 {序号}"。

`split_sections(blocks) -> list[dict]`：按 `【X】` 标记切 `kind`，标记前段落按首词归入 `现病史 / 主诉 / 查体 / 辨证 / 治法 / 处方 / 治疗效果 / 按`。

`parse_herbs(text) -> list[dict]`：正则先抓 `([\u4e00-\u9fa5、,，]+)各\s*(\d+(?:\.\d+)?)\s*(g|克|两)` 展开为每味药同剂量，再抓单味 `([\u4e00-\u9fa5]{2,4})\s*(\d+(?:\.\d+)?)\s*(g|克|两)`；剂量一律转成字符串（避开浮点误差），单位归一 `克→g`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd test && python -m pytest test_case_parser.py -v`
预期：3 passed。再跑全量：打印单元数，**必须 ≥ 220**（附录 A 记录 `【问题】` 共 228 个），打印前 3 个单元的 `title_guess` 供人工扫一眼。

- [ ] **步骤 5：Commit**

```bash
git add database/etl/case_parser.py test/test_case_parser.py
git commit -m "feat(etl): 切分方证案例单元并抽取药味剂量"
```

## 任务 4：DDL 补列 + 写入 PostgreSQL

**文件：**
- 修改：`database/pg/01-schema.sql`（`case_record` 增加 `book_id`、`node_id` 两列）
- 创建：`database/etl/import_case_book.py`
- 测试：`test/test_import_case_book.py`

- [ ] **步骤 1：编写失败的测试**

```python
# test/test_import_case_book.py
from database.etl.import_case_book import build_rows, make_ids

def test_ids_follow_project_prefix_convention():
    ids = make_ids(book_seq=4, chapter_no=2, section_no=1, unit_no=7)
    assert ids["book"] == "bk_4"
    assert ids["chapter"] == "n_c2"
    assert ids["section"] == "n_c2_s1"
    assert ids["unit"] == "n_c2_s1_u7"
    assert ids["case"] == "cs_c2_s1_u7"

def test_build_rows_produces_one_case_per_unit():
    units = [{"title_guess": "麻黄汤证", "blocks": ["现病史：无汗。", "【问题】", "1.为何？"]}]
    rows = build_rows(units, book_id="bk_4", chapter_no=2, section_no=1)
    assert len(rows["case_record"]) == 1
    assert rows["case_record"][0]["book_id"] == "bk_4"
    assert rows["case_section"][0]["kind"] == "现病史"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd test && python -m pytest test_import_case_book.py -v`
预期：FAIL，模块不存在

- [ ] **步骤 3：实现 `make_ids`、`build_rows` 与 `main()`**

`build_rows` 纯函数：输入单元列表 → 输出六张表的行字典（`book`/`book_node`/`case_record`/`case_section`/`classic_quote`/`content_unit`），不碰数据库。`main()` 负责：解析 → `build_rows` → 单事务写库（每表 `ON CONFLICT (id) DO UPDATE`）→ 打印对账表。

`database/pg/01-schema.sql` 第 64-74 行的 `case_record` 增加两列：

```sql
ALTER TABLE case_record ADD COLUMN IF NOT EXISTS book_id TEXT REFERENCES book(id);
ALTER TABLE case_record ADD COLUMN IF NOT EXISTS node_id TEXT REFERENCES book_node(id);
CREATE INDEX IF NOT EXISTS idx_case_record_book ON case_record(book_id);
```

`classic_quote` 的 `classic_id` 按单元所属章查 `classic` 表（`name='伤寒论'` 等），查不到就写 NULL 并在对账里计数。

`content_unit`：每个案例一条 `unit_type='case_full'`（content = 单元全文，`ref_type='case_record'`, `ref_id=cs_xxx`），每条条文一条 `unit_type='quote'`。

- [ ] **步骤 4：运行测试验证通过 + dry-run**

运行：`cd test && python -m pytest test_import_case_book.py -v`
预期：2 passed
运行：`cd d:\HomeWork\_KeYanShJian\HerbMind && python database/etl/import_case_book.py --dry-run`
预期：打印 `book=1 nodes=267 cases=228 sections≈1500 quotes≈N content_units≈N+M`，不写库

- [ ] **步骤 5：Commit**

```bash
git add database/pg/01-schema.sql database/etl/import_case_book.py test/test_import_case_book.py
git commit -m "feat(etl): 全量导入方证案例书并补 case_record 归属列"
```

## 任务 5：正式写库 + 向量补全

**文件：**
- 修改：`database/etl/import_case_book.py`（加 `--with-embedding` 开关）
- 参考：`database/etl/sync_content_unit.py:68-101`（`embed_batch`）

- [ ] **步骤 1：在 `import_case_book.py` 加 `--with-embedding`，完成后 `content_unit.embedding` 必须非空**

- [ ] **步骤 2：执行导入**

运行：`python database/etl/import_case_book.py --commit --with-embedding`
预期：单事务提交成功，日志打印每表写入行数与耗时

- [ ] **步骤 3：对账查询（不通过就回滚重跑）**

```sql
SELECT count(*) FROM book_node WHERE book_id='bk_4';                      -- 期望 ≥ 267
SELECT count(*) FROM case_record WHERE book_id='bk_4';                    -- 期望 228 左右
SELECT count(*) FROM content_unit WHERE book_id='bk_4';                   -- 期望 ≥ 228
SELECT count(*) FROM content_unit WHERE book_id='bk_4' AND embedding IS NULL;  -- 期望 0
SELECT count(*) FROM case_record WHERE book_id='bk_4' AND main_formula_id IS NOT NULL; -- 记录匹配率
```

- [ ] **步骤 4：抽查 3 条内容**

运行：`docker exec herbmind-v2-pg psql -U postgres -d herbmind -c "SELECT title, left(content,120) FROM content_unit WHERE book_id='bk_4' ORDER BY random() LIMIT 3"`
预期：能读出通顺的方证案例正文，无页眉页脚残留
（连接参数来自 `docker/docker-compose.infra.yml`：user=postgres / password=postgres / db=herbmind / 端口 5432）

- [ ] **步骤 5：Commit**

```bash
git add database/etl/import_case_book.py
git commit -m "feat(etl): 导入流程支持向量补全与对账输出"
```

## 任务 6：Neo4j 增 :Book / :Case 节点

**文件：**
- 修改：`database/etl/build_graph.py`
- 修改：`backend/svc-graph/src/main/java/com/herbmind/svc/graph/service/GraphQueryService.java`（标签白名单）

- [ ] **步骤 1：在 `build_graph.py` 增加第二段建图**

```cypher
MERGE (b:Book {id: $book_id}) SET b.title = $title
MERGE (c:Case {id: $case_id}) SET c.title = $case_title
MERGE (b)-[:HAS_CASE]->(c)
WITH c WHERE $formula_id IS NOT NULL
MATCH (f:Formula {id: $formula_id}) MERGE (c)-[:MAIN_FORMULA]->(f)
```

数据来源：`SELECT id,title FROM book WHERE id='bk_4'`、`SELECT id,title,main_formula_id FROM case_record WHERE book_id='bk_4'`。

- [ ] **步骤 2：放宽查询白名单**

`GraphQueryService.java:176` 的 `WHERE n:Formula OR n:Herb` 改为 `WHERE n:Formula OR n:Herb OR n:Case OR n:Book`（`208`、`487` 两处同类判断同样处理）。

- [ ] **步骤 3：执行并验证**

运行：`python database/etl/build_graph.py`
验证（Neo4j Browser 打开 http://localhost:7474，账号 neo4j，密码见 `docker/docker-compose.infra.yml` 的 `NEO4J_AUTH`）：

```cypher
MATCH (b:Book {id:'bk_4'})-[:HAS_CASE]->(c) RETURN count(c);   // 期望 ≈ 228
MATCH (c:Case)-[:MAIN_FORMULA]->(f) RETURN count(c);            // 期望 = 方名匹配成功数
```

- [ ] **步骤 4：Commit**

```bash
git add database/etl/build_graph.py backend/svc-graph/src/main/java/com/herbmind/svc/graph/service/GraphQueryService.java
git commit -m "feat(graph): 建 :Book/:Case 节点并放行新标签查询"
```

## 任务 7：前端书单不再硬编码

**文件：**
- 修改：`frontend/src/views/LibraryView.vue:95-99`（`bookTabs` 改动态）
- 修改：`frontend/src/views/HomeView.vue:96`（书名 chip 改可点）

- [ ] **步骤 1：`LibraryView` 的 `bookTabs` 改为 `getBooks()` 结果**

```ts
const bookTabs = computed(() =>
  books.value.map((b) => ({ id: b.id, label: b.title, disabled: (b.unitCount ?? 0) === 0 }))
)
```

`books` 取自 `getBooks()`；首次进入若无 `?bookId=`，默认取第一个 `unitCount > 0` 的书。

- [ ] **步骤 2：`HomeView` 的 span 改 RouterLink**

```vue
<RouterLink v-for="b in books" :key="b.id" :to="`/library?bookId=${b.id}`" :class="bookChipClass(b)">
  {{ bookChipText(b) }}
</RouterLink>
```

- [ ] **步骤 3：类型检查 + 浏览器验证**

运行：`cd frontend && npm run build`
预期：无 TS 错误
浏览器：首页 → 点击第四本书 → `/library?bookId=bk_4` → 目录树出现 4 章 → 点案例节点能看到正文

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/views/LibraryView.vue frontend/src/views/HomeView.vue
git commit -m "feat(frontend): 书单改为接口驱动，新书可在目录树切换"
```

## 任务 8：端到端验收

- [ ] **步骤 1：重启受影响服务**（BFF、svc-catalog、svc-graph、gateway）后逐层验证

```bash
curl.exe -s http://localhost:8082/internal/catalog/books            # 备注：应出现第 4 本书
curl.exe -s "http://localhost:8082/internal/catalog/tree?bookId=bk_4" # 备注：目录树 4 章
curl.exe -s http://localhost:8090/api/biz/catalog/books             # 备注：BFF R 外壳
```

- [ ] **步骤 2：页面走查三条路径**

首页书 chip → 书架 → 目录树 → 案例详情 → 条文页；图谱页搜索新书案例节点；问答页提问一个只存在新书里的词（如"烂喉痧"），确认能召回

- [ ] **步骤 3：跑既有测试确认无回归**

运行：`cd frontend && npx vitest run --config ../test/vitest.config.mts` 与 `cd test && python -m pytest . -q`
预期：32 + 52 全绿

- [ ] **步骤 4：Commit**

```bash
git commit --allow-empty -m "chore: 完成方证案例书全量导入验收"
```

---

## 附录 A：docx 结构事实（四轮扫描实测）

| 项 | 值 |
|---|---|
| 文本块总数 | 8710（含表格 78） |
| 真实表格 | 2 个（方剂比较表、证候病机表），其余 76 个是目录点线页 |
| 章节 | 4 章 / 38 节（第一章理论 3 节、伤寒论 6 节、温病学 8 节、金匮要略 21 节） |
| 单元 | 228 个 `【问题】`、232 个 `【问题解答】` |
| 关键词命中 | 组成 21、主治 66、功用 12、方名 3、用法 6、方解 4 |
| 书目引用 | 伤寒论 171、金匮要略 141、温病学 82 |
| 已知 OCR 错字 | `徬寒论`、`万证杂例研究`、`…研究消失。`（批注混入） |
| 剂量样式 | `麻黄、桂枝各 18g，杏仁10g`（合并剂量 + g/克/两 混用） |

## 附录 B：已知风险与回滚

- **回滚**：`DELETE FROM content_unit WHERE book_id='bk_4'` → `case_section`/`case_record`/`book_node` 按 `book_id` 级联删 → `book` 删 `bk_4`；Neo4j 执行 `MATCH (b:Book {id:'bk_4'}) DETACH DELETE b`。脚本需提供 `--rollback` 一键执行上述顺序。
- **向量成本**：约 228 + N 条 × 1024 维，走 siliconflow 批量接口（16 条/批），预计 20~40 次请求。
- **时间**：解析 5 分钟、写库 2 分钟、向量 10~20 分钟、建图 1 分钟，合计约 30~45 分钟（不含调试）。
