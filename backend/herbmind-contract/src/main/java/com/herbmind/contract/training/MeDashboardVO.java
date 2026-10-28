package com.herbmind.contract.training;

import java.util.List;

import com.herbmind.contract.identity.UserDto;

/**
 * 「我的 · 总览」聚合体（对齐 09 契约 13：GET /api/biz/me/dashboard）。
 *
 * 分工：
 * - svc-training 只填 stats / radar / shortcuts / timeline（user 留空）；
 * - BFF 再补 user（来自 svc-identity）—— 一次请求把整页喂满，前端不用并发三个接口。
 *
 * 字段全部 camelCase（前端直接消费，不做任何字段名转换）。
 */
public class MeDashboardVO {

    private UserDto user;

    private Stats stats;

    private List<RadarItem> radar;

    private Shortcuts shortcuts;

    private List<TimelineItem> timeline;

    public UserDto getUser() {
        return user;
    }

    public void setUser(UserDto user) {
        this.user = user;
    }

    public Stats getStats() {
        return stats;
    }

    public void setStats(Stats stats) {
        this.stats = stats;
    }

    public List<RadarItem> getRadar() {
        return radar;
    }

    public void setRadar(List<RadarItem> radar) {
        this.radar = radar;
    }

    public Shortcuts getShortcuts() {
        return shortcuts;
    }

    public void setShortcuts(Shortcuts shortcuts) {
        this.shortcuts = shortcuts;
    }

    public List<TimelineItem> getTimeline() {
        return timeline;
    }

    public void setTimeline(List<TimelineItem> timeline) {
        this.timeline = timeline;
    }

    /** 顶部四宫格：学习时长 / 连续打卡 / 综合掌握度 / 点亮的方证节点。 */
    public static class Stats {

        /** 累计学习时长（分钟） */
        private Integer totalMinutes;

        /** 连续打卡天数 */
        private Integer streakDays;

        /** 综合掌握度（0-100，取自 answer_score.total 均值） */
        private Integer mastery;

        /** 已点亮的方证节点数（练对过的不同 unit 数） */
        private Integer litNodes;

        /** 总答题数（前端用来判断"还没练过"的空态） */
        private Integer answerCount;

        public Integer getTotalMinutes() {
            return totalMinutes;
        }

        public void setTotalMinutes(Integer totalMinutes) {
            this.totalMinutes = totalMinutes;
        }

        public Integer getStreakDays() {
            return streakDays;
        }

        public void setStreakDays(Integer streakDays) {
            this.streakDays = streakDays;
        }

        public Integer getMastery() {
            return mastery;
        }

        public void setMastery(Integer mastery) {
            this.mastery = mastery;
        }

        public Integer getLitNodes() {
            return litNodes;
        }

        public void setLitNodes(Integer litNodes) {
            this.litNodes = litNodes;
        }

        public Integer getAnswerCount() {
            return answerCount;
        }

        public void setAnswerCount(Integer answerCount) {
            this.answerCount = answerCount;
        }
    }

    /** 能力雷达的一维（value 归一到 0-100）。 */
    public static class RadarItem {

        private String key;

        private String label;

        private Integer value;

        public RadarItem() {
        }

        public RadarItem(String key, String label, Integer value) {
            this.key = key;
            this.label = label;
            this.value = value;
        }

        public String getKey() {
            return key;
        }

        public void setKey(String key) {
            this.key = key;
        }

        public String getLabel() {
            return label;
        }

        public void setLabel(String label) {
            this.label = label;
        }

        public Integer getValue() {
            return value;
        }

        public void setValue(Integer value) {
            this.value = value;
        }
    }

    /** 快捷入口的三个计数。 */
    public static class Shortcuts {

        private Integer favorites;

        private Integer notes;

        private Integer wrong;

        public Integer getFavorites() {
            return favorites;
        }

        public void setFavorites(Integer favorites) {
            this.favorites = favorites;
        }

        public Integer getNotes() {
            return notes;
        }

        public void setNotes(Integer notes) {
            this.notes = notes;
        }

        public Integer getWrong() {
            return wrong;
        }

        public void setWrong(Integer wrong) {
            this.wrong = wrong;
        }
    }

    /** 成长时间轴的一条。time 是已格式化的展示文本（今天 / 昨天 / 10-09）。 */
    public static class TimelineItem {

        private String time;

        private String text;

        private String eventType;

        public TimelineItem() {
        }

        public TimelineItem(String time, String text, String eventType) {
            this.time = time;
            this.text = text;
            this.eventType = eventType;
        }

        public String getTime() {
            return time;
        }

        public void setTime(String time) {
            this.time = time;
        }

        public String getText() {
            return text;
        }

        public void setText(String text) {
            this.text = text;
        }

        public String getEventType() {
            return eventType;
        }

        public void setEventType(String eventType) {
            this.eventType = eventType;
        }
    }
}
