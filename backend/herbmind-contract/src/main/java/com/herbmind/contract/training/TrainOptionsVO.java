package com.herbmind.contract.training;

import java.util.List;

/**
 * 练习台选项（GET /api/biz/train/options）。
 *
 * 对应原型 train.html 的三排 chip：
 * - 经典/章节 → books[].title + books[].nodes[].title
 * - 模式      → modes
 * - 开始练习  → 选中节点后可练的方证数（formulaCount）
 *
 * 只有**真的挂到方证上的目录节点**才会出现在这里（否则点了没题可出）。
 */
public class TrainOptionsVO {

    private List<BookOption> books;

    private List<String> modes;

    /** 最近练习（直接喂 train.html 右下角那块） */
    private List<RecentItem> recent;

    public List<BookOption> getBooks() {
        return books;
    }

    public void setBooks(List<BookOption> books) {
        this.books = books;
    }

    public List<String> getModes() {
        return modes;
    }

    public void setModes(List<String> modes) {
        this.modes = modes;
    }

    public List<RecentItem> getRecent() {
        return recent;
    }

    public void setRecent(List<RecentItem> recent) {
        this.recent = recent;
    }

    public static class BookOption {

        private String id;

        private String title;

        private List<NodeOption> nodes;

        public BookOption() {
        }

        public BookOption(String id, String title, List<NodeOption> nodes) {
            this.id = id;
            this.title = title;
            this.nodes = nodes;
        }

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getTitle() {
            return title;
        }

        public void setTitle(String title) {
            this.title = title;
        }

        public List<NodeOption> getNodes() {
            return nodes;
        }

        public void setNodes(List<NodeOption> nodes) {
            this.nodes = nodes;
        }
    }

    public static class NodeOption {

        /** book_node.id —— 前端作为练习单元的 ref */
        private String id;

        private String title;

        /** 该节点的方证数 = 可出的题数 */
        private Integer formulaCount;

        /** 是否练过（前端给个「已练」标记） */
        private Boolean practiced;

        public NodeOption() {
        }

        public NodeOption(String id, String title, Integer formulaCount, Boolean practiced) {
            this.id = id;
            this.title = title;
            this.formulaCount = formulaCount;
            this.practiced = practiced;
        }

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getTitle() {
            return title;
        }

        public void setTitle(String title) {
            this.title = title;
        }

        public Integer getFormulaCount() {
            return formulaCount;
        }

        public void setFormulaCount(Integer formulaCount) {
            this.formulaCount = formulaCount;
        }

        public Boolean getPracticed() {
            return practiced;
        }

        public void setPracticed(Boolean practiced) {
            this.practiced = practiced;
        }
    }

    /** 最近练习一条。time 已格式化为「今天 20:14 / 昨天 / 10-09」。 */
    public static class RecentItem {

        private String sessionId;

        private String nodeTitle;

        private String mode;

        private String time;

        /** 该会话最近一次得分，没有则为 null */
        private Integer score;

        private Integer durationSeconds;

        private Boolean inWrongBook;

        public RecentItem() {
        }

        public RecentItem(String sessionId, String nodeTitle, String mode, String time,
                          Integer score, Integer durationSeconds, Boolean inWrongBook) {
            this.sessionId = sessionId;
            this.nodeTitle = nodeTitle;
            this.mode = mode;
            this.time = time;
            this.score = score;
            this.durationSeconds = durationSeconds;
            this.inWrongBook = inWrongBook;
        }

        public String getSessionId() {
            return sessionId;
        }

        public void setSessionId(String sessionId) {
            this.sessionId = sessionId;
        }

        public String getNodeTitle() {
            return nodeTitle;
        }

        public void setNodeTitle(String nodeTitle) {
            this.nodeTitle = nodeTitle;
        }

        public String getMode() {
            return mode;
        }

        public void setMode(String mode) {
            this.mode = mode;
        }

        public String getTime() {
            return time;
        }

        public void setTime(String time) {
            this.time = time;
        }

        public Integer getScore() {
            return score;
        }

        public void setScore(Integer score) {
            this.score = score;
        }

        public Integer getDurationSeconds() {
            return durationSeconds;
        }

        public void setDurationSeconds(Integer durationSeconds) {
            this.durationSeconds = durationSeconds;
        }

        public Boolean getInWrongBook() {
            return inWrongBook;
        }

        public void setInWrongBook(Boolean inWrongBook) {
            this.inWrongBook = inWrongBook;
        }
    }
}
