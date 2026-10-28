package com.herbmind.contract.training;

import java.util.List;

/**
 * 错题本（GET /api/biz/me/wrong）。
 *
 * 口径：wrong_book 里有的就是错题单元（提交时 total<60 才写入）。
 * 同时带上该单元的真实练习次数与最好成绩 —— 让人看得到「错了但后来会了」，
 * 而不是只有一个越来越旧的 last_score。
 */
public record WrongBookVO(List<Item> items, Summary summary) {

    /**
     * @param unitRef     book_node.id
     * @param nodeTitle   单元名
     * @param bookTitle   所属经典
     * @param lastScore   入库时的分数（= 触发进错题本的那次）
     * @param bestScore   该单元历史最高分
     * @param attempts    该单元累计作答次数
     * @param addedLabel  加入时间：今天 / 昨天 / 10-09
     */
    public record Item(
            String unitRef,
            String nodeTitle,
            String bookTitle,
            int lastScore,
            Integer bestScore,
            int attempts,
            String addedLabel) {
    }

    /**
     * @param total  错题单元数
     * @param cleared 其中已重新练到 60 分以上的（可以移出错题本）
     */
    public record Summary(int total, int cleared) {
    }
}
