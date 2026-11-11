package com.herbmind.svc.training.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 「我的 · 总览」的聚合查询。
 *
 * 这里全是只读的跨表统计，用 @Select 直接写 SQL 比走 BaseMapper 更直观；
 * 所有数值列都显式 ::int，避免 PG 的 BIGINT/NUMERIC 在 Java 侧变成 Long/BigDecimal。
 */
@Mapper
public interface TrainingStatMapper {

    /**
     * 答题得分均值（辨证 / 方剂 / 治法 / 总分）+ 答题总数。
     * 无答题记录时：各均值为 null、answer_count 为 0（聚合无 GROUP BY 必返回一行）。
     */
    @Select("""
            SELECT ROUND(AVG(s.syndrome_score))::int  AS syndrome,
                   ROUND(AVG(s.formula_score))::int   AS formula,
                   ROUND(AVG(s.treatment_score))::int AS treatment,
                   ROUND(AVG(s.total))::int           AS total,
                   COUNT(*)::int                      AS answer_count
            FROM answer_score s
            JOIN training_answer  a  ON a.id  = s.answer_id
            JOIN training_session ts ON ts.id = a.session_id
            WHERE ts.user_id = #{userId}
            """)
    Map<String, Object> scoreAgg(@Param("userId") String userId);

    /** 低分题数（总分 < 60），用于错题本的兜底口径。 */
    @Select("""
            SELECT COUNT(*)::int
            FROM answer_score s
            JOIN training_answer  a  ON a.id  = s.answer_id
            JOIN training_session ts ON ts.id = a.session_id
            WHERE ts.user_id = #{userId} AND s.total < 60
            """)
    Integer lowScoreCount(@Param("userId") String userId);

    /** 已点亮的方证节点：练对过的不同 unit 数（is_correct 为空视为练对，兼容旧数据）。 */
    @Select("""
            SELECT COUNT(DISTINCT unit_ref)::int
            FROM training_record
            WHERE user_id = #{userId}
              AND unit_ref IS NOT NULL
              AND COALESCE(is_correct, TRUE)
            """)
    Integer litNodes(@Param("userId") String userId);

    /** 累计学习时长（分钟）：profile 汇总值、训练记录、会话时长三者取最大，避免重复累加。 */
    @Select("""
            SELECT GREATEST(
                     COALESCE((SELECT total_minutes FROM learning_profile WHERE user_id = #{userId}), 0),
                     (SELECT COALESCE(SUM(duration_ms) / 60000, 0)::int FROM training_record  WHERE user_id = #{userId}),
                     (SELECT COALESCE(SUM(duration_ms) / 60000, 0)::int FROM training_session WHERE user_id = #{userId})
                   )::int
            """)
    Integer totalMinutes(@Param("userId") String userId);

    /** learning_profile 里已算好的连续打卡天数（没有 profile 行则为 null）。 */
    @Select("SELECT streak_days FROM learning_profile WHERE user_id = #{userId}")
    Integer profileStreak(@Param("userId") String userId);

    /** learning_profile 里缓存的雷达 JSON（形如 [{"k":"伤寒论","v":82}, ...]），没有则为 null。 */
    @Select("SELECT radar_jsonb::text FROM learning_profile WHERE user_id = #{userId}")
    String profileRadar(@Param("userId") String userId);

    /**
     * 有学习行为的日期（近 90 天，倒序）。
     * 三个来源合并：训练记录、答题提交、学习事件打点。
     */
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

    /** 快捷入口三个计数：收藏 / 笔记 / 错题本。 */
    @Select("""
            SELECT (SELECT COUNT(*) FROM user_favorite WHERE user_id = #{userId})::int AS favorites,
                   (SELECT COUNT(*) FROM user_note     WHERE user_id = #{userId})::int AS notes,
                   (SELECT COUNT(*) FROM wrong_book    WHERE user_id = #{userId})::int AS wrong
            """)
    Map<String, Object> shortcutCounts(@Param("userId") String userId);

    /**
     * 成长时间轴：答题提交 + 学习事件合并后按时间倒序。
     * day 已按用户时区格式化成 YYYY-MM-DD，Java 侧只负责换算「今天 / 昨天」。
     *
     * ★ 练习的 ref 存的是 book_node.id，这里 JOIN 出节点标题；
     *   取不到标题时退回原始 ref，绝不显示成空白（历史数据的 unit_ref 可能是自由文本）。
     */
    @Select("""
            SELECT e.event_type,
                   e.ref,
                   e.score,
                   to_char(e.created_at AT TIME ZONE #{zone}, 'YYYY-MM-DD') AS day
            FROM (
                SELECT 'practice' AS event_type,
                       COALESCE(n.title, ts.unit_ref, '') AS ref,
                       s.total AS score,
                       a.submitted_at AS created_at
                FROM training_answer a
                JOIN training_session ts ON ts.id = a.session_id
                LEFT JOIN book_node     n ON n.id = ts.unit_ref
                LEFT JOIN answer_score  s ON s.answer_id = a.id
                WHERE ts.user_id = #{userId}
                UNION ALL
                SELECT event_type,
                       COALESCE(ref, ''),
                       NULL::numeric,
                       created_at
                FROM learning_event
                WHERE user_id = #{userId}
            ) e
            ORDER BY e.created_at DESC
            LIMIT #{limit}
            """)
    List<Map<String, Object>> recentEvents(@Param("userId") String userId,
                                           @Param("zone") String zone,
                                           @Param("limit") int limit);
}
