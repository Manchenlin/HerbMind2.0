package com.herbmind.svc.identity.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 用户的「内容侧」数据：收藏 / 笔记 / 讨论。
 *
 * 为什么放在 svc-identity 而不是 svc-training：
 * 这三张表（user_favorite / user_note / discuss_*）和 app_user 同库同域，
 * 标题要 JOIN formula / case_record / classic_quote 才能显示，
 * 放训练服务会变成"跨服务的伪关联"——同一台 PG，却要两次调用再拼。
 *
 * ★ 标题解析：target_type 只有三态，用一条 SQL 三个 LEFT JOIN + COALESCE 解决，
 *   比在 Java 里 for 循环查三次清楚，也不会 N+1。
 * ★ 同样的坑：驼峰别名必须加双引号，否则 PG 折叠成小写。
 */
@Mapper
public interface UserContentMapper {

    // ------------------------------------------------------------------ 收藏

    /**
     * 收藏列表。
     *
     * subtitle 按类型取不同内容（一句话说明）：方剂取功效、医案取舌脉、条文取原文开头。
     * 这样前端不用为了"显示一行小字"再查内容域。
     */
    @Select("""
            SELECT fv.id                       AS id,
                   fv.target_type              AS "targetType",
                   CASE fv.target_type
                        WHEN 'formula' THEN '方剂'
                        WHEN 'case'    THEN '医案'
                        WHEN 'quote'   THEN '条文'
                        ELSE fv.target_type END AS "targetLabel",
                   fv.target_id                AS "targetId",
                   COALESCE(f.name,
                            c.title,
                            LEFT(q.content, 40)) AS title,
                   COALESCE(LEFT(f.efficacy, 46),
                            LEFT(c.syndrome_text, 46),
                            LEFT(q.plain_text, 46),
                            '')                AS subtitle,
                   CASE fv.target_type
                        WHEN 'formula' THEN '/formula/' || fv.target_id
                        WHEN 'case'    THEN '/case/'    || fv.target_id
                        WHEN 'quote'   THEN '/quote/'   || fv.target_id
                        ELSE '/' END        AS link,
                   TO_CHAR(fv.created_at AT TIME ZONE #{zone}, 'YYYY-MM-DD') AS "createdDay"
            FROM user_favorite fv
            LEFT JOIN formula       f ON fv.target_type = 'formula' AND f.id = fv.target_id
            LEFT JOIN case_record   c ON fv.target_type = 'case'    AND c.id = fv.target_id
            LEFT JOIN classic_quote q ON fv.target_type = 'quote'   AND q.id = fv.target_id
            WHERE fv.user_id = #{userId}
            ORDER BY fv.created_at DESC
            """)
    List<Map<String, Object>> favorites(@Param("userId") String userId,
                                        @Param("zone") String zone);

    /** 加收藏。(user_id, target_type, target_id) 唯一，重复点不报错。 */
    @Insert("""
            INSERT INTO user_favorite (user_id, target_type, target_id)
            VALUES (#{userId}, #{targetType}, #{targetId})
            ON CONFLICT (user_id, target_type, target_id) DO NOTHING
            """)
    int addFavorite(@Param("userId") String userId,
                    @Param("targetType") String targetType,
                    @Param("targetId") String targetId);

    /** 取消收藏。带 user_id 条件，防止越权删别人的。 */
    @Delete("DELETE FROM user_favorite WHERE id = #{id} AND user_id = #{userId}")
    int removeFavorite(@Param("userId") String userId, @Param("id") long id);

    // ------------------------------------------------------------------ 笔记

    /**
     * 笔记列表。targetTitle 用 COALESCE 兜底成 target_id ——
     * 内容被删了也要能显示这条笔记存在，而不是一行空白。
     */
    @Select("""
            SELECT n.id                        AS id,
                   n.target_type               AS "targetType",
                   CASE n.target_type
                        WHEN 'formula' THEN '方剂'
                        WHEN 'case'    THEN '医案'
                        WHEN 'quote'   THEN '条文'
                        ELSE n.target_type END AS "targetLabel",
                   n.target_id                 AS "targetId",
                   COALESCE(f.name, c.title, LEFT(q.content, 30), n.target_id) AS "targetTitle",
                   COALESCE(n.content, '')     AS content,
                   CASE n.target_type
                        WHEN 'formula' THEN '/formula/' || n.target_id
                        WHEN 'case'    THEN '/case/'    || n.target_id
                        WHEN 'quote'   THEN '/quote/'   || n.target_id
                        ELSE '/' END           AS link,
                   TO_CHAR(n.created_at AT TIME ZONE #{zone}, 'YYYY-MM-DD') AS "createdDay"
            FROM user_note n
            LEFT JOIN formula       f ON n.target_type = 'formula' AND f.id = n.target_id
            LEFT JOIN case_record   c ON n.target_type = 'case'    AND c.id = n.target_id
            LEFT JOIN classic_quote q ON n.target_type = 'quote'   AND q.id = n.target_id
            WHERE n.user_id = #{userId}
            ORDER BY n.created_at DESC
            """)
    List<Map<String, Object>> notes(@Param("userId") String userId,
                                    @Param("zone") String zone);

    @Insert("""
            INSERT INTO user_note (user_id, target_type, target_id, content)
            VALUES (#{userId}, #{targetType}, #{targetId}, #{content})
            """)
    int insertNote(@Param("userId") String userId,
                   @Param("targetType") String targetType,
                   @Param("targetId") String targetId,
                   @Param("content") String content);

    @Delete("DELETE FROM user_note WHERE id = #{id} AND user_id = #{userId}")
    int deleteNote(@Param("userId") String userId, @Param("id") long id);

    // ------------------------------------------------------------------ 讨论

    /**
     * 话题列表（可按对象过滤）。
     *
     * 楼层不在这里 JOIN —— 一个话题可能有几十层，JOIN 出来再分组去重反而更绕。
     * 服务层拿到话题列表后，再用一条 SQL 按 topic_id IN (...) 取最新几层，两次查询搞定。
     */
    @Select("""
            <script>
            SELECT t.id            AS id,
                   COALESCE(NULLIF(t.title, ''), '未命名话题') AS title,
                   t.target_type   AS "targetType",
                   t.target_id     AS "targetId",
                   COALESCE(NULLIF(u.nickname, ''), u.username, '匿名') AS author,
                   TO_CHAR(t.created_at AT TIME ZONE #{zone}, 'YYYY-MM-DD HH24:MI') AS "createdAt",
                   (SELECT COUNT(*)::int FROM discuss_floor df WHERE df.topic_id = t.id) AS "floorCount"
            FROM discuss_topic t
            LEFT JOIN app_user u ON u.id = t.user_id
            <where>
              <if test="targetType != null and targetType != ''">
                AND t.target_type = #{targetType}
              </if>
              <if test="targetId != null and targetId != ''">
                AND t.target_id = #{targetId}
              </if>
            </where>
            ORDER BY t.created_at DESC
            LIMIT 30
            </script>
            """)
    List<Map<String, Object>> topics(@Param("targetType") String targetType,
                                     @Param("targetId") String targetId,
                                     @Param("zone") String zone);

    /**
     * 话题的前 3 层（首楼 + 两条回复），够渲染列表卡片的预览。
     * 按时间正序取，服务层截断到 3 条 —— 原型里话题卡就是"1 楼 / 2 楼"这种读法。
     */
    @Select("""
            <script>
            SELECT df.id        AS id,
                   df.topic_id  AS "topicId",
                   COALESCE(NULLIF(u.nickname, ''), u.username, '匿名') AS author,
                   COALESCE(df.content, '') AS content,
                   df.is_pinned AS "isPinned",
                   TO_CHAR(df.created_at AT TIME ZONE #{zone}, 'YYYY-MM-DD') AS "createdDay"
            FROM discuss_floor df
            LEFT JOIN app_user u ON u.id = df.user_id
            WHERE df.topic_id IN
              <foreach collection="topicIds" item="id" open="(" separator="," close=")">#{id}</foreach>
            ORDER BY df.created_at
            </script>
            """)
    List<Map<String, Object>> floorsOf(@Param("topicIds") List<String> topicIds,
                                       @Param("zone") String zone);

    @Insert("""
            INSERT INTO discuss_topic (id, target_type, target_id, title, user_id, created_at)
            VALUES (#{id}, #{targetType}, #{targetId}, #{title}, #{userId}, now())
            """)
    int insertTopic(@Param("id") String id,
                    @Param("userId") String userId,
                    @Param("targetType") String targetType,
                    @Param("targetId") String targetId,
                    @Param("title") String title);

    @Insert("""
            INSERT INTO discuss_floor (id, topic_id, user_id, content, created_at)
            VALUES (#{id}, #{topicId}, #{userId}, #{content}, now())
            """)
    int insertFloor(@Param("id") String id,
                    @Param("topicId") String topicId,
                    @Param("userId") String userId,
                    @Param("content") String content);

    /** 校验话题归属（回帖前确认话题存在）。 */
    @Select("SELECT id FROM discuss_topic WHERE id = #{topicId}")
    String topicExists(@Param("topicId") String topicId);
}
