package com.herbmind.contract.training;

import java.util.List;

/**
 * 我的方证库（GET /api/biz/me/collection）。
 *
 * 「库」= 我练过的方证，按**方**聚合（不是按单元）：
 * 因为一个单元下有多个方，人才会想知道「这个方我到底会不会」。
 *
 * 方 id 从会话 id 里解出来（会话 id 格式 s_&lt;formulaId&gt;_&lt;8位随机&gt;），
 * 这样不用给 training_session 加字段（DDL 归域1维护，不该为了一张报表改表）。
 *
 * @param status 已掌握（最好成绩>=80）/ 待巩固（>=60）/ 需重练（&lt;60）
 */
public record FormulaLibVO(List<Item> items, Summary summary) {

    public record Item(
            String formulaId,
            String name,
            String nodeTitle,
            String bookTitle,
            int practices,
            int bestScore,
            int lastScore,
            String lastLabel,
            String status) {
    }

    /**
     * @param total     练过的方数
     * @param mastered  已掌握
     * @param learning  待巩固
     * @param weak      需重练
     */
    public record Summary(int total, int mastered, int learning, int weak) {
    }
}
