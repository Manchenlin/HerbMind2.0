package com.herbmind.svc.training.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 案例盲盒 + 背诵打卡的查询。
 *
 * 与 PracticeStatMapper 的分工：那个管「按方证单元练」，这里管两种额外练法。
 *
 * ★ 同样的坑：PG 会把未加引号的别名折叠成小写，驼峰别名一律用双引号包起来。
 */
@Mapper
public interface ExtraPracticeMapper {

    // ------------------------------------------------------------------ 案例盲盒

    /**
     * 随机抽一个「可揭晓」的医案。
     *
     * 三个必须条件，少一个就会抽出残缺的盲盒：
     * ① 案例挂了主方（main_formula_id）—— 否则没答案可揭晓
     * ② 该方有药味组成（formula_herb）—— 否则处方栏是空的
     * ③ 有「案例原文」段落且够长 —— 否则题面只剩一个标题，没法辨证
     */
    @Select("""
            SELECT c.id                 AS "caseId",
                   c.title              AS title,
                   c.syndrome_text      AS exam,
                   c.main_formula_id    AS "formulaId",
                   f.name               AS "formulaName",
                   n.id                 AS "nodeId",
                   n.title              AS "nodeTitle",
                   b.title              AS "bookTitle",
                   LEFT(sec.content, 420) AS illness
            FROM case_record c
            JOIN formula f      ON f.id = c.main_formula_id
            JOIN book_node n    ON n.id = f.node_id
            JOIN book b         ON b.id = n.book_id
            CROSS JOIN LATERAL (
                    SELECT cs.content
                    FROM case_section cs
                    WHERE cs.case_id = c.id AND cs.kind = '案例原文'
                    ORDER BY cs.seq
                    LIMIT 1
            ) sec
            WHERE EXISTS (SELECT 1 FROM formula_herb h
                          WHERE h.formula_id = f.id
                            AND h.herb_name !~ '[汤见：:（）()]'
                            AND LENGTH(h.herb_name) BETWEEN 1 AND 6)
              AND LENGTH(COALESCE(sec.content, '')) > 80
            ORDER BY random()
            LIMIT 1
            """)
    Map<String, Object> randomCase();

    /** 盲盒战绩：只算真的提交过作答的盲盒会话，抽了没答的不算。 */
    @Select("""
            SELECT COUNT(*)::int             AS drawn,
                   ROUND(AVG(s.total))::int  AS "avgScore"
            FROM training_session ts
            JOIN training_answer a ON a.session_id = ts.id
            JOIN answer_score    s ON s.answer_id  = a.id
            WHERE ts.user_id = #{userId} AND ts.mode = '盲盒'
            """)
    Map<String, Object> blindboxStats(@Param("userId") String userId);

    /** 揭晓答案：方名 / 辨证 / 治法 / 出处。 */
    @Select("""
            SELECT f.name          AS "formulaName",
                   f.syndrome_text AS "syndromeText",
                   f.efficacy      AS efficacy,
                   f.page          AS page,
                   n.title         AS "nodeTitle",
                   b.title         AS "bookTitle"
            FROM case_record c
            JOIN formula   f ON f.id = c.main_formula_id
            LEFT JOIN book_node n ON n.id = f.node_id
            LEFT JOIN book      b ON b.id = n.book_id
            WHERE c.id = #{caseId}
            """)
    Map<String, Object> caseAnswer(@Param("caseId") String caseId);

    /** 揭晓答案时的处方明细（药味 + 剂量）。剔掉「方名交叉引用」那种假药味。 */
    @Select("""
            SELECT herb_name AS herb, dose, unit
            FROM formula_herb
            WHERE formula_id = #{formulaId}
              AND herb_name !~ '[汤见：:（）()]'
              AND LENGTH(herb_name) BETWEEN 1 AND 6
            ORDER BY seq
            """)
    List<Map<String, Object>> caseHerbs(@Param("formulaId") String formulaId);

    // ------------------------------------------------------------------ 背诵打卡

    /**
     * 待背列表：到期的排最前，没背过的次之，其余按下次复习时间。
     *
     * 一次最多给 20 条 —— 一屏能看完，也不会把 568 条条文全推给前端。
     */
    @Select("""
            SELECT q.id            AS "quoteId",
                   q.article_no    AS "articleNo",
                   cl.name         AS "classicName",
                   q.content       AS content,
                   q.plain_text    AS "plainText",
                   r.last_result   AS "lastResult",
                   (r.next_review_at IS NULL OR r.next_review_at <= now()) AS due,
                   CASE WHEN r.next_review_at IS NULL THEN NULL
                        ELSE TO_CHAR(r.next_review_at AT TIME ZONE #{zone}, 'MM-DD') END AS "reviewDay"
            FROM classic_quote q
            JOIN classic cl ON cl.id = q.classic_id
            LEFT JOIN recite_record r ON r.quote_id = q.id AND r.user_id = #{userId}
            WHERE q.content IS NOT NULL AND LENGTH(q.content) BETWEEN 12 AND 600
            ORDER BY (r.next_review_at IS NULL OR r.next_review_at <= now()) DESC,
                     r.next_review_at NULLS FIRST,
                     CAST(SUBSTRING(q.id FROM '[0-9]+') AS INTEGER)
            LIMIT #{limit}
            """)
    List<Map<String, Object>> reciteItems(@Param("userId") String userId,
                                          @Param("zone") String zone,
                                          @Param("limit") int limit);

    /** 背诵总览：可背总数 / 今日到期 / 已背熟。 */
    @Select("""
            SELECT (SELECT COUNT(*) FROM classic_quote
                    WHERE content IS NOT NULL AND LENGTH(content) BETWEEN 12 AND 600)::int AS total,
                   (SELECT COUNT(*) FROM classic_quote q
                    LEFT JOIN recite_record r ON r.quote_id = q.id AND r.user_id = #{userId}
                    WHERE q.content IS NOT NULL AND LENGTH(q.content) BETWEEN 12 AND 600
                      AND (r.next_review_at IS NULL OR r.next_review_at <= now()))::int AS due,
                   (SELECT COUNT(*) FROM recite_record
                    WHERE user_id = #{userId} AND last_result = '对')::int AS mastered
            """)
    Map<String, Object> reciteStats(@Param("userId") String userId);

    /** 单条条文（判分与对照用）。 */
    @Select("""
            SELECT q.id AS "quoteId", q.article_no AS "articleNo", q.content, q.plain_text AS "plainText",
                   cl.name AS "classicName"
            FROM classic_quote q
            LEFT JOIN classic cl ON cl.id = q.classic_id
            WHERE q.id = #{quoteId}
            """)
    Map<String, Object> quoteById(@Param("quoteId") String quoteId);

    /** 上次背诵结果（决定下一次间隔时用得到上次状态，这里只用来算是否「连对」）。 */
    @Select("""
            SELECT last_result AS "lastResult", ease, next_review_at AS "nextReviewAt"
            FROM recite_record WHERE user_id = #{userId} AND quote_id = #{quoteId}
            """)
    Map<String, Object> reciteRecord(@Param("userId") String userId,
                                     @Param("quoteId") String quoteId);

    /**
     * 写入背诵记录。(user_id, quote_id) 是主键，重背就更新。
     * next_review_at 由服务层按分数算好传进来 —— 间隔规则必须确定性，不能靠 now() 随机。
     */
    @Insert("""
            INSERT INTO recite_record (user_id, quote_id, ease, next_review_at, last_result)
            VALUES (#{userId}, #{quoteId}, #{ease}, #{nextReviewAt}::timestamptz, #{lastResult})
            ON CONFLICT (user_id, quote_id) DO UPDATE
               SET ease = EXCLUDED.ease,
                   next_review_at = EXCLUDED.next_review_at,
                   last_result = EXCLUDED.last_result
            """)
    int upsertRecite(@Param("userId") String userId,
                     @Param("quoteId") String quoteId,
                     @Param("ease") double ease,
                     @Param("nextReviewAt") String nextReviewAt,
                     @Param("lastResult") String lastResult);

    /**
     * 学习打点。背诵要落一条 event_type='recite'：
     * 连续打卡天数（DashboardService.calcStreak）读的就是 learning_event，
     * 不写的话"背了一晚上，打卡天数不动"。
     */
    @Insert("""
            INSERT INTO learning_event (user_id, event_type, ref, created_at)
            VALUES (#{userId}, #{eventType}, #{ref}, now())
            """)
    int insertEvent(@Param("userId") String userId,
                    @Param("eventType") String eventType,
                    @Param("ref") String ref);

    /** 有学习行为的日期（近 90 天，倒序）——与 TrainingStatMapper 同一口径，供打卡天数复用。 */
    @Select("""
            SELECT DISTINCT d::text AS d FROM (
                SELECT (created_at AT TIME ZONE #{zone})::date AS d
                FROM training_record WHERE user_id = #{userId}
                UNION
                SELECT (a.submitted_at AT TIME ZONE #{zone})::date
                FROM training_answer a
                JOIN training_session ts ON ts.id = a.session_id
                WHERE ts.user_id = #{userId}
                UNION
                SELECT (created_at AT TIME ZONE #{zone})::date
                FROM learning_event WHERE user_id = #{userId}
            ) t
            ORDER BY d DESC
            LIMIT 90
            """)
    List<String> activeDays(@Param("userId") String userId, @Param("zone") String zone);
}
