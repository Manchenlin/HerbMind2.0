package com.herbmind.contract.training;

import java.util.List;

/**
 * 学习档案聚合体（对齐 09 契约：GET /api/biz/me/profile）。
 *
 * 与「我的·总览」的区别：总览是概览卡片，档案是**按经典拆解** + 学习路径 + 薄弱点。
 *
 * 数据来源全部真实：
 * - classics  ← training_session.unit_ref → book_node → book（所以 unit_ref 必须存节点 ID）
 * - radar     ← 复用总览口径（辨证/方剂/治法/广度/坚持）
 * - weakPoints← answer_score.miss_jsonb 里被漏掉症状的高频词
 * - path      ← 同书优先、尚未练习的目录节点
 */
public class MeProfileVO {

    private List<MeDashboardVO.RadarItem> radar;

    /** 三经典掌握度（按书拆解） */
    private List<ClassicItem> classics;

    /** 推荐学习路径 */
    private List<PathItem> path;

    /** 薄弱点（漏答症状的高频词） */
    private List<String> weakPoints;

    /** 概览数字，给页面顶部用 */
    private Summary summary;

    public List<MeDashboardVO.RadarItem> getRadar() {
        return radar;
    }

    public void setRadar(List<MeDashboardVO.RadarItem> radar) {
        this.radar = radar;
    }

    public List<ClassicItem> getClassics() {
        return classics;
    }

    public void setClassics(List<ClassicItem> classics) {
        this.classics = classics;
    }

    public List<PathItem> getPath() {
        return path;
    }

    public void setPath(List<PathItem> path) {
        this.path = path;
    }

    public List<String> getWeakPoints() {
        return weakPoints;
    }

    public void setWeakPoints(List<String> weakPoints) {
        this.weakPoints = weakPoints;
    }

    public Summary getSummary() {
        return summary;
    }

    public void setSummary(Summary summary) {
        this.summary = summary;
    }

    /**
     * 一部经典（一本书）的掌握度。
     *
     * mastery 的口径：**有答题分数就用均分**；只有练习记录没有分数则用正确率；
     * 两者都没有则为 0 且 status = 未开始 —— 不用任何估算值填充。
     */
    public static class ClassicItem {

        private String key;

        private String title;

        /** 0-100 */
        private Integer mastery;

        /** 已练过的目录节点数 */
        private Integer practiced;

        /** 该书可练的目录节点总数 */
        private Integer total;

        private Integer answers;

        /** 已掌握 / 进行中 / 未开始 */
        private String status;

        public ClassicItem() {
        }

        public ClassicItem(String key, String title, Integer mastery, Integer practiced,
                           Integer total, Integer answers, String status) {
            this.key = key;
            this.title = title;
            this.mastery = mastery;
            this.practiced = practiced;
            this.total = total;
            this.answers = answers;
            this.status = status;
        }

        public String getKey() {
            return key;
        }

        public void setKey(String key) {
            this.key = key;
        }

        public String getTitle() {
            return title;
        }

        public void setTitle(String title) {
            this.title = title;
        }

        public Integer getMastery() {
            return mastery;
        }

        public void setMastery(Integer mastery) {
            this.mastery = mastery;
        }

        public Integer getPracticed() {
            return practiced;
        }

        public void setPracticed(Integer practiced) {
            this.practiced = practiced;
        }

        public Integer getTotal() {
            return total;
        }

        public void setTotal(Integer total) {
            this.total = total;
        }

        public Integer getAnswers() {
            return answers;
        }

        public void setAnswers(Integer answers) {
            this.answers = answers;
        }

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }
    }

    /** 学习路径的一步。 */
    public static class PathItem {

        /** 序号，从 1 开始 */
        private Integer step;

        private String nodeId;

        private String title;

        private String bookTitle;

        /** 该节点下的方证数 */
        private Integer formulaCount;

        /** 推荐理由（人话，前端直接展示） */
        private String reason;

        public PathItem() {
        }

        public PathItem(Integer step, String nodeId, String title, String bookTitle,
                        Integer formulaCount, String reason) {
            this.step = step;
            this.nodeId = nodeId;
            this.title = title;
            this.bookTitle = bookTitle;
            this.formulaCount = formulaCount;
            this.reason = reason;
        }

        public Integer getStep() {
            return step;
        }

        public void setStep(Integer step) {
            this.step = step;
        }

        public String getNodeId() {
            return nodeId;
        }

        public void setNodeId(String nodeId) {
            this.nodeId = nodeId;
        }

        public String getTitle() {
            return title;
        }

        public void setTitle(String title) {
            this.title = title;
        }

        public String getBookTitle() {
            return bookTitle;
        }

        public void setBookTitle(String bookTitle) {
            this.bookTitle = bookTitle;
        }

        public Integer getFormulaCount() {
            return formulaCount;
        }

        public void setFormulaCount(Integer formulaCount) {
            this.formulaCount = formulaCount;
        }

        public String getReason() {
            return reason;
        }

        public void setReason(String reason) {
            this.reason = reason;
        }
    }

    /** 档案页顶部的概览数字。 */
    public static class Summary {

        private Integer answers;

        private Integer litNodes;

        private Integer streakDays;

        private Integer minutes;

        private Integer mastery;

        public Summary() {
        }

        public Summary(Integer answers, Integer litNodes, Integer streakDays,
                       Integer minutes, Integer mastery) {
            this.answers = answers;
            this.litNodes = litNodes;
            this.streakDays = streakDays;
            this.minutes = minutes;
            this.mastery = mastery;
        }

        public Integer getAnswers() {
            return answers;
        }

        public void setAnswers(Integer answers) {
            this.answers = answers;
        }

        public Integer getLitNodes() {
            return litNodes;
        }

        public void setLitNodes(Integer litNodes) {
            this.litNodes = litNodes;
        }

        public Integer getStreakDays() {
            return streakDays;
        }

        public void setStreakDays(Integer streakDays) {
            this.streakDays = streakDays;
        }

        public Integer getMinutes() {
            return minutes;
        }

        public void setMinutes(Integer minutes) {
            this.minutes = minutes;
        }

        public Integer getMastery() {
            return mastery;
        }

        public void setMastery(Integer mastery) {
            this.mastery = mastery;
        }
    }
}
