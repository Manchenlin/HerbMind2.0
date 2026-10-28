package com.herbmind.svc.training.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 「我的」下面四个页面的查询：评分报告 / 错题本 / 我的方证库 / 学习路径。
 *
 * 全部只读 + 一个删除（移出错题本）。
 *
 * ★ 会话 ID 里藏着方剂 ID（格式 s_&lt;formulaId&gt;_&lt;8位随机&gt;）。
 *   方证库要「按方聚合」，但又不想为了报表给 training_session 加字段（DDL 归域1维护），
 *   于是用正则把方 id 抠出来：substring(ts.id from '^s_(f_[0-9]+)_')。
 *   约定写在 PracticeService.newSessionId() 那一侧，改格式时两处要一起改。
 */
@Mapper
public interface MeLibraryMapper {

    // ------------------------------------------------------------------ 评分报告

    /**
     * 单条作答的全貌。LEFT JOIN 一路下来，任何一个关联断了都不该让整页 404 ——
     * 少了方名就显示不出来方名，但分数该显示还得显示。
     */
    @Select("""
            SELECT a.id                    AS "answerId",
                   a.session_id            AS "sessionId",
                   a.user_syndrome         AS "userSyndrome",
                   a.user_treatment        AS "userTreatment",
                   a.user_prescription_jsonb::text AS "userPrescription",
                   TO_CHAR(a.submitted_at AT TIME ZONE #{zone}, 'YYYY-MM-DD HH24:MI') AS "submittedAt",
                   (COALESCE(ts.duration_ms, 0) / 1000)::int AS "durationSeconds",
                   s.total                 AS total,
                   s.syndrome_score        AS "syndromeScore",
                   s.formula_score         AS "formulaScore",
                   s.treatment_score       AS "treatmentScore",
                   COALESCE(s.hit_jsonb,   '[]'::jsonb)::text AS hit,
                   COALESCE(s.miss_jsonb,  '[]'::jsonb)::text AS miss,
                   COALESCE(s.extra_jsonb, '[]'::jsonb)::text AS extra,
                   n.title                 AS "nodeTitle",
                   b.title                 AS "bookTitle",
                   f.id                    AS "formulaId",
                   f.name                  AS "formulaName",
                   f.efficacy              AS efficacy,
                   f.syndrome_text         AS "stdSyndrome",
                   c.id                    AS "caseId"
            FROM training_answer a
            JOIN training_session ts ON ts.id = a.session_id
            LEFT JOIN answer_score s ON s.answer_id = a.id
            LEFT JOIN book_node   n ON n.id = ts.unit_ref
            LEFT JOIN book        b ON b.id = n.book_id
            LEFT JOIN formula     f ON f.id = SUBSTRING(ts.id FROM '^s_(f_[0-9]+)_')
            LEFT JOIN LATERAL (
                    SELECT c1.id FROM case_record c1
                    WHERE c1.main_formula_id = f.id
                    ORDER BY c1.id
                    LIMIT 1
            ) c ON TRUE
            WHERE a.id = #{answerId} AND ts.user_id = #{userId}
            """)
    Map<String, Object> report(@Param("userId") String userId,
                               @Param("answerId") String answerId,
                               @Param("zone") String zone);

    /** 报告页的原著处方（药味 + 剂量）。剔掉「方名交叉引用」那种假药味。 */
    @Select("""
            SELECT herb_name AS herb, dose, unit
            FROM formula_herb
            WHERE formula_id = #{formulaId}
              AND herb_name !~ '[汤见：:（）()]'
              AND LENGTH(herb_name) BETWEEN 1 AND 6
            ORDER BY seq
            """)
    List<Map<String, Object>> herbs(@Param("formulaId") String formulaId);

    // ------------------------------------------------------------------ 错题本

    /**
     * 错题本列表。
     *
     * 带两件事让「错题」不至于变成死档案：
     * - bestScore：这个单元历史最高分（后来练会了也看得见）
     * - attempts：练了几次
     * 两个都用相关子查询算，数据量是按用户走的，不需要预先物化。
     *
     * ★ 注意「已清」的判定在服务层：bestScore 比 last_score 高且及格才算真的练回来了。
     *   只判 bestScore>=60 会把「当初就是 63 分进的错题本」也算成已清 —— 那是自欺。
     */
    @Select("""
            SELECT w.unit_ref                     AS "unitRef",
                   COALESCE(n.title, w.unit_ref)  AS "nodeTitle",
                   COALESCE(b.title, '')          AS "bookTitle",
                   ROUND(COALESCE(w.last_score, 0))::int AS "lastScore",
                   (SELECT ROUND(MAX(s.total))::int
                    FROM training_answer a
                    JOIN training_session ts ON ts.id = a.session_id
                    JOIN answer_score     s  ON s.answer_id = a.id
                    WHERE ts.user_id = w.user_id AND ts.unit_ref = w.unit_ref) AS "bestScore",
                   (SELECT COUNT(*)::int
                    FROM training_answer a
                    JOIN training_session ts ON ts.id = a.session_id
                    WHERE ts.user_id = w.user_id AND ts.unit_ref = w.unit_ref) AS attempts,
                   TO_CHAR(w.added_at AT TIME ZONE #{zone}, 'YYYY-MM-DD') AS "addedDay"
            FROM wrong_book w
            LEFT JOIN book_node n ON n.id = w.unit_ref
            LEFT JOIN book      b ON b.id = n.book_id
            WHERE w.user_id = #{userId}
            ORDER BY w.last_score ASC, w.added_at DESC
            """)
    List<Map<String, Object>> wrongBook(@Param("userId") String userId,
                                        @Param("zone") String zone);

    @Delete("DELETE FROM wrong_book WHERE user_id = #{userId} AND unit_ref = #{unitRef}")
    int deleteWrong(@Param("userId") String userId, @Param("unitRef") String unitRef);

    // ---------------------------------------------------------------- 我的方证库

    /**
     * 按**方**聚合的练习记录。
     *
     * lastScore 用 ARRAY_AGG(... ORDER BY submitted_at DESC)[1] 取最近一次 ——
     * PG 没有 "first_value over window + group by" 的简写，数组下标最直接。
     */
    @Select("""
            SELECT a."formulaId"          AS "formulaId",
                   f.name                 AS name,
                   COALESCE(n.title, '')  AS "nodeTitle",
                   COALESCE(b.title, '')  AS "bookTitle",
                   COUNT(*)::int          AS practices,
                   ROUND(MAX(s.total))::int AS "bestScore",
                   (ARRAY_AGG(ROUND(s.total)::int ORDER BY a.submitted_at DESC))[1] AS "lastScore",
                   TO_CHAR(MAX(a.submitted_at) AT TIME ZONE #{zone}, 'YYYY-MM-DD') AS "lastDay"
            FROM (
                SELECT ans.id, ans.submitted_at,
                       SUBSTRING(ts.id FROM '^s_(f_[0-9]+)_') AS "formulaId"
                FROM training_answer ans
                JOIN training_session ts ON ts.id = ans.session_id
                WHERE ts.user_id = #{userId}
            ) a
            JOIN answer_score s ON s.answer_id = a.id
            JOIN formula      f ON f.id = a."formulaId"
            LEFT JOIN book_node n ON n.id = f.node_id
            LEFT JOIN book      b ON b.id = n.book_id
            GROUP BY a."formulaId", f.name, n.title, b.title
            ORDER BY MAX(a.submitted_at) DESC
            """)
    List<Map<String, Object>> collection(@Param("userId") String userId,
                                         @Param("zone") String zone);

    // ------------------------------------------------------------------ 学习路径

    /** 已练过的单元（带最近得分，用于「已完成」段）。 */
    @Select("""
            SELECT n.id                 AS "nodeId",
                   n.title              AS title,
                   b.title              AS "bookTitle",
                   COUNT(DISTINCT f.id)::int AS "formulaCount",
                   MAX(r.created_at)    AS "lastAt",
                   (SELECT ROUND(AVG(s.total))::int
                    FROM training_answer a
                    JOIN training_session ts ON ts.id = a.session_id
                    JOIN answer_score     s  ON s.answer_id = a.id
                    WHERE ts.user_id = #{userId} AND ts.unit_ref = n.id) AS score
            FROM training_record r
            JOIN book_node n ON n.id = r.unit_ref
            JOIN book      b ON b.id = n.book_id
            LEFT JOIN formula f ON f.node_id = n.id
            WHERE r.user_id = #{userId}
            GROUP BY n.id, n.title, b.title
            ORDER BY MAX(r.created_at)
            """)
    List<Map<String, Object>> practicedSteps(@Param("userId") String userId);

    /** 全库可练单元总数（路径进度分母）。与练习台同一判据，否则进度会算出 >100%。 */
    @Select("""
            SELECT COUNT(DISTINCT n.id)::int
            FROM book_node n
            JOIN formula f ON f.node_id = n.id
            WHERE EXISTS (SELECT 1 FROM formula_herb h
                          WHERE h.formula_id = f.id
                            AND h.herb_name !~ '[汤见：:（）()]'
                            AND LENGTH(h.herb_name) BETWEEN 1 AND 6)
            """)
    Integer practiceableTotal();
}
