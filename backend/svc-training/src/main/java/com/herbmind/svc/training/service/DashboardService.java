package com.herbmind.svc.training.service;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herbmind.contract.training.MeDashboardVO;
import com.herbmind.svc.training.mapper.TrainingStatMapper;

/**
 * 「我的 · 总览」统计口径（全部来自真实表，不做假数据）：
 *
 * - 累计学习时长 = max(profile.total_minutes, training_record 累计, training_session 累计)
 * - 连续打卡     = profile.streak_days；没有 profile 时按有学习行为的日期现算
 * - 综合掌握度   = answer_score.total 均值
 * - 点亮节点数   = 练对过的不同 unit 数
 * - 能力雷达     = 辨证/方剂/治法 三项均分 + 广度（点亮节点/20）+ 坚持（打卡/14）
 * - 快捷入口     = 收藏 / 笔记 / 错题本 计数
 * - 成长时间轴   = 答题提交 + learning_event 打点，合并倒序
 */
@Service
public class DashboardService {

    private static final Logger log = LoggerFactory.getLogger(DashboardService.class);

    private static final DateTimeFormatter MM_DD = DateTimeFormatter.ofPattern("MM-dd");

    /** 能力雷达的满分口径：点亮 20 个方证算「广度」满格，连续打卡 7 天算「坚持」满格。 */
    private static final int LIT_NODE_TARGET = 20;
    private static final int STREAK_TARGET = 7;

    private final TrainingStatMapper mapper;
    private final String zone;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public DashboardService(TrainingStatMapper mapper,
                            @Value("${herbmind.zone:Asia/Shanghai}") String zone) {
        this.mapper = mapper;
        this.zone = zone;
    }

    public MeDashboardVO dashboard(String userId) {
        Map<String, Object> agg = mapper.scoreAgg(userId);

        int answerCount = intOf(agg, "answer_count");
        int syndrome = intOf(agg, "syndrome");
        int formula = intOf(agg, "formula");
        int treatment = intOf(agg, "treatment");
        int mastery = intOf(agg, "total");

        int minutes = zeroIfNull(mapper.totalMinutes(userId));
        int litNodes = zeroIfNull(mapper.litNodes(userId));

        Integer cachedStreak = mapper.profileStreak(userId);
        int streak = (cachedStreak != null && cachedStreak > 0) ? cachedStreak : calcStreak(userId);

        MeDashboardVO vo = new MeDashboardVO();
        vo.setStats(buildStats(minutes, streak, mastery, litNodes, answerCount));
        vo.setRadar(buildRadar(userId, syndrome, formula, treatment, litNodes, streak));
        vo.setShortcuts(buildShortcuts(userId));
        vo.setTimeline(buildTimeline(userId));
        return vo;
    }

    private MeDashboardVO.Stats buildStats(int minutes, int streak, int mastery, int lit, int answers) {
        MeDashboardVO.Stats s = new MeDashboardVO.Stats();
        s.setTotalMinutes(minutes);
        s.setStreakDays(streak);
        s.setMastery(clamp(mastery));
        s.setLitNodes(lit);
        s.setAnswerCount(answers);
        return s;
    }

    /**
     * 雷达优先用 learning_profile.radar_jsonb（若别的流程已离线算好），
     * 否则按答题分项现算 —— 保证页面永远有真实数据可看。
     */
    private List<MeDashboardVO.RadarItem> buildRadar(String userId, int syndrome, int formula,
                                                     int treatment, int lit, int streak) {
        String cached = mapper.profileRadar(userId);
        List<MeDashboardVO.RadarItem> fromProfile = parseRadar(cached);
        if (fromProfile != null && !fromProfile.isEmpty()) {
            return fromProfile;
        }

        List<MeDashboardVO.RadarItem> radar = new ArrayList<>(5);
        radar.add(new MeDashboardVO.RadarItem("syndrome", "辨证", clamp(syndrome)));
        radar.add(new MeDashboardVO.RadarItem("formula", "方剂", clamp(formula)));
        radar.add(new MeDashboardVO.RadarItem("treatment", "治法", clamp(treatment)));
        radar.add(new MeDashboardVO.RadarItem("breadth", "广度", clamp(lit * 100 / LIT_NODE_TARGET)));
        radar.add(new MeDashboardVO.RadarItem("persist", "坚持", clamp(streak * 100 / STREAK_TARGET)));
        return radar;
    }

    /**
     * 解析 learning_profile.radar_jsonb —— 兼容 [{"k":"伤寒论","v":82}] 与
     * [{"key":"syndrome","label":"辨证","value":78}] 两种写法。
     * 解析失败不抛异常：总览页不能因为一条脏缓存就白屏。
     */
    private List<MeDashboardVO.RadarItem> parseRadar(String json) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            JsonNode root = objectMapper.readTree(json);
            if (!root.isArray() || root.isEmpty()) {
                return null;
            }
            List<MeDashboardVO.RadarItem> list = new ArrayList<>(root.size());
            for (JsonNode n : root) {
                String label = text(n, "label", text(n, "k", ""));
                String key = text(n, "key", "d" + list.size());
                int value = n.has("value") ? n.path("value").asInt(0) : n.path("v").asInt(0);
                if (label.isBlank()) {
                    continue;
                }
                list.add(new MeDashboardVO.RadarItem(key, label, clamp(value)));
            }
            return list;
        } catch (JsonProcessingException e) {
            log.warn("radar_jsonb 解析失败，回退到答题分项：{}", e.getMessage());
            return null;
        }
    }

    private static String text(JsonNode n, String field, String fallback) {
        JsonNode v = n.path(field);
        return v.isTextual() && !v.asText().isBlank() ? v.asText() : fallback;
    }

    private MeDashboardVO.Shortcuts buildShortcuts(String userId) {
        Map<String, Object> c = mapper.shortcutCounts(userId);
        int wrong = intOf(c, "wrong");
        if (wrong == 0) {
            // 错题本还没写数据时，退化为「低分题数」，避免入口永远显示 0
            wrong = zeroIfNull(mapper.lowScoreCount(userId));
        }
        MeDashboardVO.Shortcuts s = new MeDashboardVO.Shortcuts();
        s.setFavorites(intOf(c, "favorites"));
        s.setNotes(intOf(c, "notes"));
        s.setWrong(wrong);
        return s;
    }

    private List<MeDashboardVO.TimelineItem> buildTimeline(String userId) {
        List<Map<String, Object>> rows = mapper.recentEvents(userId, zone, 6);
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        List<MeDashboardVO.TimelineItem> items = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            String day = str(r.get("day"));
            String type = str(r.get("event_type"));
            String ref = str(r.get("ref"));
            String score = r.get("score") == null ? null : String.valueOf(Math.round(
                    Double.parseDouble(String.valueOf(r.get("score")))));

            items.add(new MeDashboardVO.TimelineItem(
                    dayLabel(day, today),
                    describe(type, ref, score),
                    type));
        }
        return items;
    }

    /** 把 ISO 日期换成「今天 / 昨天 / 10-09」。 */
    private String dayLabel(String iso, LocalDate today) {
        if (iso == null || iso.length() < 10) {
            return "";
        }
        LocalDate d;
        try {
            d = LocalDate.parse(iso.substring(0, 10));
        } catch (RuntimeException e) {
            return iso;
        }
        if (d.equals(today)) {
            return "今天";
        }
        if (d.equals(today.minusDays(1))) {
            return "昨天";
        }
        return d.format(MM_DD);
    }

    private String describe(String type, String ref, String score) {
        String target = (ref == null || ref.isBlank()) ? "" : "「" + ref + "」";
        if (type == null) {
            return "完成一次学习";
        }
        switch (type) {
            case "practice":
                return score == null
                        ? "完成一次练习" + target
                        : "练习" + target + "，得 " + score + " 分";
            case "view":
                return "浏览了" + target;
            case "favorite":
                return "收藏了" + target;
            case "note":
                return "在" + target + "写了一条笔记";
            case "recite":
                return "背诵打卡" + target;
            case "ask":
                return "向智能问答提问" + target;
            default:
                return "完成一次" + type + target;
        }
    }

    /** 连续打卡：从今天（今天没练则从昨天）往回数，遇到断档即止。 */
    private int calcStreak(String userId) {
        List<String> days = mapper.activeDays(userId, zone);
        if (days == null || days.isEmpty()) {
            return 0;
        }
        Set<LocalDate> set = new HashSet<>();
        for (String d : days) {
            try {
                set.add(LocalDate.parse(d));
            } catch (RuntimeException ignored) {
                // 脏数据直接跳过
            }
        }
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        LocalDate cursor = set.contains(today) ? today : today.minusDays(1);
        int streak = 0;
        while (set.contains(cursor)) {
            streak++;
            cursor = cursor.minusDays(1);
        }
        return streak;
    }

    private static int clamp(int v) {
        return Math.max(0, Math.min(100, v));
    }

    private static int zeroIfNull(Integer v) {
        return v == null ? 0 : v;
    }

    private static int intOf(Map<String, Object> m, String key) {
        if (m == null) {
            return 0;
        }
        Object v = m.get(key);
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

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }
}
