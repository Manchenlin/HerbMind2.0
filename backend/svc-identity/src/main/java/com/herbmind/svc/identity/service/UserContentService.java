package com.herbmind.svc.identity.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.herbmind.contract.identity.DiscussVO;
import com.herbmind.contract.identity.FavoriteVO;
import com.herbmind.contract.identity.NoteVO;
import com.herbmind.contract.identity.UserContentReq;
import com.herbmind.svc.identity.mapper.UserContentMapper;

/**
 * 收藏 / 笔记 / 讨论的业务层。
 *
 * 三件事都不复杂，但有几个必须守住的边界：
 * ① targetType 白名单（formula / case / quote）—— 别的值直接拒，不靠前端自觉；
 * ② 所有写操作都带 user_id 条件 —— 删别人的收藏不是"参数错误"，是越权；
 * ③ 空内容不落库 —— 空笔记、空帖子会让列表变成一堆空白卡。
 */
@Service
public class UserContentService {

    /** 允许挂载的对象类型（与 user_favorite.target_type 的注释一致）。 */
    private static final Set<String> TYPES = Set.of("formula", "case", "quote");

    /**
     * 话题允许额外挂一个「综合」类型（target_id 固定 "-"）。
     * 讨论区需要一个"不属于任何方剂/医案"的公共板块，
     * 否则发起话题就必须先挑一个内容对象 —— 用户只想随便问问时不成立。
     */
    private static final Set<String> TOPIC_TYPES = Set.of("formula", "case", "quote", "general");

    private static final DateTimeFormatter HH_MM = DateTimeFormatter.ofPattern("HH:mm");
    private static final DateTimeFormatter MM_DD_HM = DateTimeFormatter.ofPattern("MM-dd HH:mm");
    private static final DateTimeFormatter MM_DD = DateTimeFormatter.ofPattern("MM-dd");

    private final UserContentMapper mapper;
    private final String zone;

    public UserContentService(UserContentMapper mapper,
                              @Value("${herbmind.zone:Asia/Shanghai}") String zone) {
        this.mapper = mapper;
        this.zone = zone;
    }

    // ------------------------------------------------------------------ 收藏

    public FavoriteVO favorites(String userId) {
        List<Map<String, Object>> rows = mapper.favorites(userId, zone);
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        List<FavoriteVO.Item> items = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            items.add(new FavoriteVO.Item(
                    longOf(r.get("id")),
                    str(r.get("targetType")),
                    str(r.get("targetLabel")),
                    str(r.get("targetId")),
                    nullToEmpty(str(r.get("title"))).isBlank()
                            ? str(r.get("targetId"))
                            : str(r.get("title")),
                    nullToEmpty(str(r.get("subtitle"))),
                    str(r.get("link")),
                    dayLabel(str(r.get("createdDay")), today)));
        }
        return new FavoriteVO(items, items.size());
    }

    @Transactional
    public FavoriteVO addFavorite(String userId, UserContentReq.Favorite req) {
        if (req == null) {
            throw new IllegalArgumentException("缺少收藏内容");
        }
        String type = requireType(req.targetType());
        String targetId = requireTargetId(req.targetId());
        mapper.addFavorite(userId, type, targetId);
        return favorites(userId);
    }

    @Transactional
    public FavoriteVO removeFavorite(String userId, long id) {
        mapper.removeFavorite(userId, id);
        return favorites(userId);
    }

    // ------------------------------------------------------------------ 笔记

    public NoteVO notes(String userId) {
        List<Map<String, Object>> rows = mapper.notes(userId, zone);
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        List<NoteVO.Item> items = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            items.add(new NoteVO.Item(
                    longOf(r.get("id")),
                    str(r.get("targetType")),
                    str(r.get("targetLabel")),
                    str(r.get("targetId")),
                    nullToEmpty(str(r.get("targetTitle"))),
                    nullToEmpty(str(r.get("content"))),
                    str(r.get("link")),
                    dayLabel(str(r.get("createdDay")), today)));
        }
        return new NoteVO(items, items.size());
    }

    @Transactional
    public NoteVO saveNote(String userId, UserContentReq.Note req) {
        if (req == null) {
            throw new IllegalArgumentException("缺少笔记内容");
        }
        String content = req.content() == null ? "" : req.content().trim();
        if (content.isEmpty()) {
            throw new IllegalArgumentException("笔记不能是空的");
        }
        String type = requireType(req.targetType());
        String targetId = requireTargetId(req.targetId());
        mapper.insertNote(userId, type, targetId, content);
        return notes(userId);
    }

    @Transactional
    public NoteVO removeNote(String userId, long id) {
        mapper.deleteNote(userId, id);
        return notes(userId);
    }

    // ------------------------------------------------------------------ 讨论

    public DiscussVO discuss(String targetType, String targetId) {
        List<Map<String, Object>> rows = mapper.topics(targetType, targetId, zone);
        if (rows.isEmpty()) {
            return new DiscussVO(List.of(), 0);
        }
        List<String> ids = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            ids.add(str(r.get("id")));
        }

        // 一次取回所有话题的楼层，再在内存里按 topicId 归组（每个话题只留前 3 层做预览）
        Map<String, List<DiscussVO.Floor>> grouped = new LinkedHashMap<>();
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        for (Map<String, Object> f : mapper.floorsOf(ids, zone)) {
            String topicId = str(f.get("topicId"));
            List<DiscussVO.Floor> list = grouped.computeIfAbsent(topicId, k -> new ArrayList<>());
            if (list.size() >= 3) {
                continue;
            }
            list.add(new DiscussVO.Floor(
                    str(f.get("id")),
                    nullToEmpty(str(f.get("author"))),
                    nullToEmpty(str(f.get("content"))),
                    timeLabel(str(f.get("createdDay")), today),
                    Boolean.TRUE.equals(f.get("isPinned"))));
        }

        List<DiscussVO.Topic> topics = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            String id = str(r.get("id"));
            topics.add(new DiscussVO.Topic(
                    id,
                    nullToEmpty(str(r.get("title"))),
                    str(r.get("targetType")),
                    str(r.get("targetId")),
                    nullToEmpty(str(r.get("author"))),
                    timeLabel(str(r.get("createdAt")), today),
                    false,
                    intOf(r.get("floorCount")),
                    grouped.getOrDefault(id, List.of())));
        }
        return new DiscussVO(topics, topics.size());
    }

    @Transactional
    public DiscussVO createTopic(String userId, UserContentReq.Topic req) {
        if (req == null) {
            throw new IllegalArgumentException("缺少话题内容");
        }
        String title = req.title() == null ? "" : req.title().trim();
        if (title.isEmpty()) {
            throw new IllegalArgumentException("话题标题不能为空");
        }
        String type = req.targetType() == null || req.targetType().isBlank()
                ? "general" : req.targetType().trim();
        if (!TOPIC_TYPES.contains(type)) {
            throw new IllegalArgumentException("不支持的对象类型：" + req.targetType());
        }
        String targetId = "general".equals(type) ? "-" : requireTargetId(req.targetId());

        String topicId = "t_" + shortId();
        mapper.insertTopic(topicId, userId, type, targetId, title);
        String content = req.content() == null ? "" : req.content().trim();
        if (!content.isEmpty()) {
            // 首楼就是发帖正文，这样列表卡片上立刻能看到内容，不用点进去
            mapper.insertFloor("df_" + shortId(), topicId, userId, content);
        }
        return discuss(type, targetId);
    }

    @Transactional
    public DiscussVO reply(String userId, String topicId, UserContentReq.Floor req) {
        if (topicId == null || topicId.isBlank()) {
            throw new IllegalArgumentException("缺少话题 ID");
        }
        String content = req == null || req.content() == null ? "" : req.content().trim();
        if (content.isEmpty()) {
            throw new IllegalArgumentException("回复不能为空");
        }
        if (mapper.topicExists(topicId) == null) {
            throw new IllegalArgumentException("话题不存在或已被删除");
        }
        mapper.insertFloor("df_" + shortId(), topicId, userId, content);

        // 回帖后重新拉这个话题所在的列表；targetType/targetId 从话题本身取不到就返回全部
        return discuss(null, null);
    }

    // ------------------------------------------------------------------ 工具

    private static String requireType(String raw) {
        String t = raw == null ? "" : raw.trim();
        if (!TYPES.contains(t)) {
            throw new IllegalArgumentException("不支持的对象类型：" + raw);
        }
        return t;
    }

    private static String requireTargetId(String raw) {
        String id = raw == null ? "" : raw.trim();
        if (id.isEmpty()) {
            throw new IllegalArgumentException("缺少对象 ID");
        }
        return id;
    }

    private static String shortId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 10);
    }

    /** 只有日期时显示 今天 / 昨天 / 10-09。 */
    private String dayLabel(String iso, LocalDate today) {
        if (iso == null || iso.length() < 10) {
            return "";
        }
        try {
            LocalDate d = LocalDate.parse(iso.substring(0, 10));
            if (d.equals(today)) {
                return "今天";
            }
            if (d.equals(today.minusDays(1))) {
                return "昨天";
            }
            return d.format(MM_DD);
        } catch (RuntimeException e) {
            return iso;
        }
    }

    /** 带时分时显示 今天 14:05 / 昨天 09:12 / 10-09 20:14。 */
    private String timeLabel(String raw, LocalDate today) {
        if (raw == null || raw.length() < 10) {
            return "";
        }
        if (raw.length() < 16) {
            return dayLabel(raw, today);
        }
        try {
            LocalDateTime t = LocalDateTime.parse(raw.replace(' ', 'T'));
            if (t.toLocalDate().equals(today)) {
                return "今天 " + t.format(HH_MM);
            }
            if (t.toLocalDate().equals(today.minusDays(1))) {
                return "昨天 " + t.format(HH_MM);
            }
            return t.format(MM_DD_HM);
        } catch (RuntimeException e) {
            return raw;
        }
    }

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    private static long longOf(Object v) {
        if (v == null) {
            return 0L;
        }
        if (v instanceof Number n) {
            return n.longValue();
        }
        try {
            return Long.parseLong(v.toString());
        } catch (NumberFormatException e) {
            return 0L;
        }
    }

    private static int intOf(Object v) {
        if (v == null) {
            return 0;
        }
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(v.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
