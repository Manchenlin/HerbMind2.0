package com.herbmind.svc.training.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

/**
 * 练习台 + 学习档案的查询。
 *
 * 与 TrainingStatMapper 的分工：
 * - TrainingStatMapper：总览页的全局统计（时长/打卡/雷达）
 * - 本接口：**按目录节点与按书拆解**的统计、出题、作答落库
 *
 * ★ 核心约定：practice 的 unit_ref 存 **book_node.id**（有方剂挂载的 category 节点），
 *   不是证候名。这样「练习记录 → 目录节点 → 书」才连得起来，三经典掌握度才有真实分母。
 *
 * ★ 坑：PG 会把未加引号的别名折叠成小写（bookId → bookid），
 *   MyBatis 返回 Map 时 key 就是小写。所以**驼峰别名一律用双引号包起来**。
 */
@Mapper
public interface PracticeStatMapper {

    /**
     * 所有**真正可练**的目录节点。
     *
     * 两个过滤条件都是必须的，缺一个就会出现"点进去没题"或"答完必得 0 分"：
     * ① 节点下要挂了方剂（否则没东西可出题）
     * ② 方剂要有 formula_herb 组成（否则药味比对没有标准答案，怎么答都是 0）
     *
     * ★ 现状（2026-10-28）：`formula_herb` 只覆盖 186/245 个方剂，
     *   伤寒论 20 个单元里 18 个没有药味数据 —— 所以练习台只会显示真正能练的单元，
     *   不显示"看起来能点但答不了"的假入口。数据补齐后这个过滤自然放宽。
     *
     * ★ 排序：book_node.seq 全是 0（数据层没填），真实顺序编码在 id 里（n_g1…n_g32），
     *   对应标题的「一、二、三…」，所以按 id 尾部数字排；直接按字符串排会把 n_g10 排到 n_g2 前。
     *
     * ★ 为什么要过滤 herb_name：数据里有 15 条 formula_herb 的「药味」其实是**方名交叉引用**，
     *   例如 f_17 栀子豉汤 只有一行 herb_name='栀子豉汤。'，f_81 是「犀角地黄汤(方见春温节)」。
     *   不过滤的话，出题会拿「栀子豉汤。」当标准药味 —— 用户怎么写都判 0 分，
     *   盲盒揭晓还会显示「处方：栀子豉汤。」这种明显错误的内容。
     *   判据：中药名最长 6 字，且不会含 汤/见/括号/冒号。真正有药味的方剂 179 个（原 186 − 7 条纯引用）。
     *   数据补齐后（ETL 侧把交叉引用展开成实际组成）这条过滤可以去掉。
     */
    @Select("""
            SELECT n.book_id             AS "bookId",
                   b.title               AS "bookTitle",
                   n.id                  AS "nodeId",
                   n.title               AS "nodeTitle",
                   COUNT(DISTINCT f.id)::int AS "formulaCount"
            FROM book_node n
            JOIN book        b ON b.id = n.book_id
            JOIN formula     f ON f.node_id = n.id
            JOIN formula_herb h ON h.formula_id = f.id
                 AND h.herb_name !~ '[汤见：:（）()]' AND LENGTH(h.herb_name) BETWEEN 1 AND 6
            GROUP BY n.book_id, b.title, n.id, n.title
            ORDER BY n.book_id,
                     CAST(SUBSTRING(n.id FROM '[0-9]+') AS INTEGER)
            """)
    List<Map<String, Object>> practiceNodes();

    /** 用户练过的节点 ID（去重）。 */
    @Select("""
            SELECT DISTINCT unit_ref
            FROM training_record
            WHERE user_id = #{userId} AND unit_ref IS NOT NULL
            """)
    List<String> practicedNodeIds(@Param("userId") String userId);

    /**
     * 用户每本书已练节点数 + 平均分。
     * 平均分只统计**真有分数**的答题（answer_score 存在才计入），没有分数的会话不虚构 0 分。
     */
    @Select("""
            SELECT n.book_id             AS "bookId",
                   COUNT(DISTINCT n.id)::int AS practiced,
                   ROUND(AVG(s.total))::int  AS "avgScore",
                   COUNT(s.id)::int          AS answers
            FROM training_session ts
            JOIN book_node n ON n.id = ts.unit_ref
            LEFT JOIN training_answer a ON a.session_id = ts.id
            LEFT JOIN answer_score   s ON s.answer_id  = a.id
            WHERE ts.user_id = #{userId}
            GROUP BY n.book_id
            """)
    List<Map<String, Object>> practicedByBook(@Param("userId") String userId);

    /**
     * 薄弱点：被漏掉（miss_jsonb）的症状词，按出现频次倒序。
     * 用 LATERAL 展开 jsonb 数组 —— 只在 miss 非空时才有行。
     */
    @Select("""
            SELECT w.word AS word, COUNT(*)::int AS cnt
            FROM answer_score s
            JOIN training_answer  a  ON a.id  = s.answer_id
            JOIN training_session ts ON ts.id = a.session_id
            CROSS JOIN LATERAL jsonb_array_elements_text(COALESCE(s.miss_jsonb, '[]'::jsonb)) AS w(word)
            WHERE ts.user_id = #{userId}
            GROUP BY w.word
            ORDER BY cnt DESC, w.word
            LIMIT #{limit}
            """)
    List<Map<String, Object>> weakWords(@Param("userId") String userId, @Param("limit") int limit);

    /**
     * 推荐学习路径：**同书优先**、尚未练习、方证多的节点排前面。
     * 排序里那个 EXISTS 是「这本书我已经练过别的节点了吗」——练过的书继续往下推，学习不断档。
     */
    @Select("""
            SELECT n.id             AS "nodeId",
                   n.title          AS "nodeTitle",
                   b.title          AS "bookTitle",
                   COUNT(f.id)::int AS "formulaCount"
            FROM book_node n
            JOIN book b    ON b.id = n.book_id
            JOIN formula f ON f.node_id = n.id
            WHERE NOT EXISTS (
                    SELECT 1 FROM training_record r
                    WHERE r.user_id = #{userId} AND r.unit_ref = n.id)
              AND EXISTS (SELECT 1 FROM formula_herb h
                          WHERE h.formula_id = f.id
                            AND h.herb_name !~ '[汤见：:（）()]'
                            AND LENGTH(h.herb_name) BETWEEN 1 AND 6)
            GROUP BY n.id, n.title, b.title, n.book_id
            ORDER BY (EXISTS (
                        SELECT 1
                        FROM training_record r2
                        JOIN book_node n2 ON n2.id = r2.unit_ref
                        WHERE r2.user_id = #{userId} AND n2.book_id = n.book_id)) DESC,
                     COUNT(f.id) DESC,
                     CAST(SUBSTRING(n.id FROM '[0-9]+') AS INTEGER)
            LIMIT #{limit}
            """)
    List<Map<String, Object>> pathCandidates(@Param("userId") String userId, @Param("limit") int limit);

    /**
     * 最近练习。时间已按用户时区格式化成 yyyy-MM-dd HH:mm，Java 侧只换算「今天 / 昨天」。
     * inWrongBook 用 wrong_book 是否存在该 unit_ref 判断。
     */
    @Select("""
            SELECT ts.id                         AS "sessionId",
                   COALESCE(n.title, ts.unit_ref) AS "nodeTitle",
                   COALESCE(ts.mode, '先思后看')   AS mode,
                   TO_CHAR(ts.started_at AT TIME ZONE #{zone}, 'YYYY-MM-DD HH24:MI') AS day,
                   ROUND(AVG(s.total))::int       AS score,
                   (COALESCE(ts.duration_ms, 0) / 1000)::int AS "durationSeconds",
                   EXISTS (SELECT 1 FROM wrong_book w
                           WHERE w.user_id = ts.user_id AND w.unit_ref = ts.unit_ref) AS "inWrongBook"
            FROM training_session ts
            LEFT JOIN book_node      n ON n.id = ts.unit_ref
            LEFT JOIN training_answer a ON a.session_id = ts.id
            LEFT JOIN answer_score   s ON s.answer_id  = a.id
            WHERE ts.user_id = #{userId}
            GROUP BY ts.id, n.title, ts.unit_ref, ts.mode, ts.started_at, ts.duration_ms, ts.user_id
            ORDER BY ts.started_at DESC
            LIMIT #{limit}
            """)
    List<Map<String, Object>> recentSessions(@Param("userId") String userId,
                                             @Param("zone") String zone,
                                             @Param("limit") int limit);

    /** 会话 → 所属节点与模式（提交作答时定位标准答案用）。 */
    @Select("""
            SELECT ts.unit_ref        AS "nodeId",
                   COALESCE(ts.mode, '先思后看') AS mode,
                   n.title            AS "nodeTitle",
                   b.title            AS "bookTitle",
                   GREATEST(0, EXTRACT(EPOCH FROM (now() - ts.started_at)))::int AS "elapsedSeconds"
            FROM training_session ts
            LEFT JOIN book_node n ON n.id = ts.unit_ref
            LEFT JOIN book      b ON b.id = n.book_id
            WHERE ts.id = #{sessionId} AND ts.user_id = #{userId}
            """)
    Map<String, Object> sessionInfo(@Param("sessionId") String sessionId,
                                    @Param("userId") String userId);

    /**
     * 出题：该节点下的方证，关联一条案例做舌脉。
     *
     * ★ 只取有 formula_herb 组成的方剂 —— 没有组成就没有标准答案，药味分必然为 0，
     *   出这种题等于坑用户。组成是数据层的事，补齐后会自动恢复可练。
     */
    @Select("""
            SELECT f.id            AS "formulaId",
                   f.name          AS "formulaName",
                   f.syndrome_text AS symptoms,
                   f.efficacy      AS efficacy,
                   c.id            AS "caseId",
                   c.syndrome_text AS signs,
                   n.title         AS "nodeTitle",
                   b.title         AS "bookTitle"
            FROM formula f
            JOIN book_node n ON n.id = f.node_id
            JOIN book      b ON b.id = n.book_id
            LEFT JOIN LATERAL (
                    SELECT c1.id, c1.syndrome_text
                    FROM case_record c1
                    WHERE c1.main_formula_id = f.id
                    ORDER BY c1.id
                    LIMIT 1
            ) c ON TRUE
            WHERE f.node_id = #{nodeId}
              AND EXISTS (SELECT 1 FROM formula_herb h
                          WHERE h.formula_id = f.id
                            AND h.herb_name !~ '[汤见：:（）()]'
                            AND LENGTH(h.herb_name) BETWEEN 1 AND 6)
            ORDER BY f.id
            """)
    List<Map<String, Object>> nodeQuestions(@Param("nodeId") String nodeId);

    /** 标准药味清单（评分用）。同样剔掉「方名交叉引用」那种假药味。 */
    @Select("""
            SELECT herb_name AS herb, dose, unit, seq
            FROM formula_herb
            WHERE formula_id = #{formulaId}
              AND herb_name !~ '[汤见：:（）()]'
              AND LENGTH(herb_name) BETWEEN 1 AND 6
            ORDER BY seq
            """)
    List<Map<String, Object>> formulaHerbs(@Param("formulaId") String formulaId);

    /** 单道题的标准答案（提交评分时用）。 */
    @Select("""
            SELECT f.id            AS "formulaId",
                   f.name          AS "formulaName",
                   f.syndrome_text AS symptoms,
                   f.efficacy      AS efficacy,
                   n.title         AS "nodeTitle",
                   b.title         AS "bookTitle"
            FROM formula f
            LEFT JOIN book_node n ON n.id = f.node_id
            LEFT JOIN book      b ON b.id = n.book_id
            WHERE f.id = #{formulaId}
            """)
    Map<String, Object> formulaDetail(@Param("formulaId") String formulaId);

    // ---------------- 落库 ----------------

    @Insert("""
            INSERT INTO training_session (id, user_id, unit_ref, mode, started_at, duration_ms)
            VALUES (#{id}, #{userId}, #{unitRef}, #{mode}, now(), NULL)
            """)
    int insertSession(@Param("id") String id,
                      @Param("userId") String userId,
                      @Param("unitRef") String unitRef,
                      @Param("mode") String mode);

    @Insert("""
            INSERT INTO training_answer (id, session_id, user_syndrome, user_prescription_jsonb, user_treatment, submitted_at)
            VALUES (#{id}, #{sessionId}, #{syndrome}, #{prescriptionJson}::jsonb, #{treatment}, now())
            """)
    int insertAnswer(@Param("id") String id,
                     @Param("sessionId") String sessionId,
                     @Param("syndrome") String syndrome,
                     @Param("treatment") String treatment,
                     @Param("prescriptionJson") String prescriptionJson);

    @Insert("""
            INSERT INTO answer_score (id, answer_id, syndrome_score, formula_score, treatment_score, total,
                                      hit_jsonb, miss_jsonb, extra_jsonb)
            VALUES (#{id}, #{answerId}, #{syndromeScore}, #{formulaScore}, #{treatmentScore}, #{total},
                    #{hitJson}::jsonb, #{missJson}::jsonb, #{extraJson}::jsonb)
            """)
    int insertScore(@Param("id") String id,
                    @Param("answerId") String answerId,
                    @Param("syndromeScore") int syndromeScore,
                    @Param("formulaScore") int formulaScore,
                    @Param("treatmentScore") int treatmentScore,
                    @Param("total") int total,
                    @Param("hitJson") String hitJson,
                    @Param("missJson") String missJson,
                    @Param("extraJson") String extraJson);

    /**
     * 练习记录。时长直接从会话表取（会话开始时没写时长，提交时才结算），
     * 避免前端传一个可伪造的耗时。
     */
    @Insert("""
            INSERT INTO training_record (user_id, unit_ref, submitted_syndrome, is_correct, duration_ms, created_at)
            VALUES (#{userId}, #{unitRef}, #{syndrome}, #{correct},
                    COALESCE((SELECT duration_ms FROM training_session WHERE id = #{sessionId}), 0), now())
            """)
    int insertRecord(@Param("userId") String userId,
                     @Param("sessionId") String sessionId,
                     @Param("unitRef") String unitRef,
                     @Param("syndrome") String syndrome,
                     @Param("correct") boolean correct);

    /** 会话结束补时长。 */
    @Update("""
            UPDATE training_session SET duration_ms = #{durationMs}
            WHERE id = #{sessionId} AND user_id = #{userId}
            """)
    int updateDuration(@Param("sessionId") String sessionId,
                       @Param("userId") String userId,
                       @Param("durationMs") long durationMs);

    /** 低分进错题本：主键是 (user_id, unit_ref)，冲突时更新为最新分数。 */
    @Insert("""
            INSERT INTO wrong_book (user_id, unit_ref, last_score)
            VALUES (#{userId}, #{unitRef}, #{score})
            ON CONFLICT (user_id, unit_ref) DO UPDATE SET last_score = EXCLUDED.last_score
            """)
    int upsertWrongBook(@Param("userId") String userId,
                        @Param("unitRef") String unitRef,
                        @Param("score") int score);
}
