-- ============================================================================
-- HerbMind 数据库演示脚本
-- 用法：
--   docker cp thinkForProject\track\instruction\demo.sql herbmind-v2-pg:/tmp/demo.sql
--   docker exec -it herbmind-v2-pg psql -U postgres -d herbmind -f /tmp/demo.sql
--
-- 说明：
--   1. 只读查询 + 一段 BEGIN ... ROLLBACK 的插入演示；
--   2. 演示数据不会留在库中；
--   3. 新库在 public，旧库在 legacy。
-- ============================================================================

\pset pager off

\echo ''
\echo '=== 1. 两个模式各有多少张表 ==='
select table_schema, count(*) as tables
from information_schema.tables
where table_schema in ('public','legacy')
group by table_schema
order by table_schema;

\echo ''
\echo '=== 2. 新库 public：30 张表 ==='
\dt public.*

\echo ''
\echo '=== 3. 旧库 legacy：41 张表（只列前 15 张） ==='
select table_name
from information_schema.tables
where table_schema='legacy'
order by table_name
limit 15;

\echo ''
\echo '=== 4. 题型白名单（初始化数据） ==='
select code, name, enabled from public.question_type order by code;

\echo ''
\echo '=== 5. 关键表结构：content_unit ==='
\d public.content_unit

\echo ''
\echo '=== 6. 关键表结构：question ==='
\d public.question

\echo ''
\echo '=== 7. 关键表结构：data_defect ==='
\d public.data_defect

\echo ''
\echo '=== 8. 约束与索引统计 ==='
select 'public_tables' as item, count(*)::text as value
  from information_schema.tables where table_schema='public'
union all select 'legacy_tables', count(*)::text
  from information_schema.tables where table_schema='legacy'
union all select 'public_fks', count(*)::text
  from pg_constraint c
  join pg_class t on t.oid=c.conrelid
  join pg_namespace n on n.oid=t.relnamespace
  where n.nspname='public' and c.contype='f'
union all select 'public_cascade_fks', count(*)::text
  from pg_constraint c
  join pg_class t on t.oid=c.conrelid
  join pg_namespace n on n.oid=t.relnamespace
  where n.nspname='public' and c.contype='f' and c.confdeltype='c'
union all select 'public_non_pk_indexes', count(*)::text
  from pg_indexes where schemaname='public' and indexname not like 'pk\_%'
union all select 'question_types', count(*)::text from public.question_type
union all select 'public_search_tsv_cols', count(*)::text
  from information_schema.columns
  where table_schema='public' and table_name='content_unit' and column_name='search_tsv';

\echo ''
\echo '=== 9. 新旧库对照：search_tsv 只存在于旧库 ==='
select 'public' as schema_name, count(*) as has_search_tsv
from information_schema.columns
where table_schema='public' and table_name='content_unit' and column_name='search_tsv'
union all
select 'legacy', count(*)
from information_schema.columns
where table_schema='legacy' and table_name='content_unit' and column_name='search_tsv';

\echo ''
\echo '=== 10. 旧库数据量 ==='
select 'book' as table_name, count(*) as rows from legacy.book
union all select 'content_unit', count(*) from legacy.content_unit
union all select 'formula', count(*) from legacy.formula
union all select 'formula_herb', count(*) from legacy.formula_herb
union all select 'case_record', count(*) from legacy.case_record
union all select 'book_node', count(*) from legacy.book_node;

\echo ''
\echo '=== 11. 事务内插入演示：书目 -> 篇 -> 单元 -> 方 -> 药 -> 组成 -> 提及 -> 题 ==='
begin;

insert into public.book (id, name, author, edition)
values ('demo-book', '演示书目', '演示作者', '演示版');

insert into public.chapter (id, book_id, name, level, seq)
values ('demo-ch', 'demo-book', '演示篇', 1, 1);

insert into public.content_unit
  (id, book_id, chapter_id, seq, display_text, norm_text, source_nature)
values
  ('demo-u1', 'demo-book', 'demo-ch', 1, '桂枝汤', '桂枝汤', '典籍原文');

insert into public.formula (id, book_id, name, norm_name)
values ('demo-f1', 'demo-book', '桂枝汤', '桂枝汤');

insert into public.herb (id, name, norm_name)
values ('demo-h1', '桂枝', '桂枝');

insert into public.formula_herb (id, formula_id, herb_id, dosage_text, seq)
values ('demo-fh1', 'demo-f1', 'demo-h1', '三两', 1);

insert into public.mention (id, unit_id, formula_id, is_primary)
values ('demo-m1', 'demo-u1', 'demo-f1', true);

insert into public.question
  (id, type, stem, answer_key, fingerprint)
values
  ('demo-q1', '选择题', '演示题干', 'A', 'demo-fp-1');

insert into public.question_unit (id, question_id, unit_id, ord)
values ('demo-qu1', 'demo-q1', 'demo-u1', 1);

\echo '--- 插入后的关联查询 ---'
select b.name as book,
       c.name as chapter,
       u.display_text as unit_text,
       f.name as formula,
       h.name as herb,
       fh.dosage_text
from public.book b
join public.chapter c on c.book_id = b.id
join public.content_unit u on u.chapter_id = c.id
join public.mention m on m.unit_id = u.id
join public.formula f on f.id = m.formula_id
join public.formula_herb fh on fh.formula_id = f.id
join public.herb h on h.id = fh.herb_id
where b.id = 'demo-book';

rollback;

\echo ''
\echo '=== 12. 回滚后确认：演示数据没有留下 ==='
select
  (select count(*) from public.book where id='demo-book') as demo_books,
  (select count(*) from public.content_unit where id='demo-u1') as demo_units,
  (select count(*) from public.question where id='demo-q1') as demo_questions;

\echo ''
\echo '=== 演示结束 ==='
