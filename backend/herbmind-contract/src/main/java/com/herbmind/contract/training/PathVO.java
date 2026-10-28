package com.herbmind.contract.training;

import java.util.List;

/**
 * 学习路径（GET /api/biz/me/path）。
 *
 * 与「学习档案」里的 `path` 的区别：档案里只给 3 步建议，这一页给**完整全程**：
 * 已完成的（带真实得分）在前，待练的（按同书优先 + 方证数倒序）在后。
 *
 * 不写入 study_path 表 —— 路径是**算出来的**，不是一张会过期的快照；
 * 一旦落库，练完一个单元就得同步一次，很容易变成假数据。
 */
public record PathVO(int practiced, int total, int percent, List<Step> done, List<Step> todo) {

    /**
     * @param seq          第几步（done 与 todo 各自从 1 编号，前端显示成两段）
     * @param nodeId       book_node.id
     * @param title        单元名
     * @param bookTitle    所属经典
     * @param formulaCount 该单元方证数
     * @param score        已练节点的最近得分；未练为 null
     * @param reason       推荐理由（后端拼好的中文）
     * @param state        done / doing / todo
     */
    public record Step(
            int seq,
            String nodeId,
            String title,
            String bookTitle,
            int formulaCount,
            Integer score,
            String reason,
            String state) {
    }
}
