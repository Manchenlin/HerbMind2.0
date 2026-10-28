package com.herbmind.contract.training;

/**
 * 案例盲盒（POST /api/biz/train/blindbox）。
 *
 * ★ 抽盲盒**不建会话**：没作答就不该在「最近练习」里留一条空记录。
 *   用户在盲盒里选「我也答一遍」时，才带 formulaId 去开一个真会话（mode=盲盒），
 *   这样练习统计、错题本、评分报告全部复用同一条链路，不用为盲盒单写一套。
 *
 * ★ 题面里不含方名 —— 揭晓答案走单独的 GET .../answer，这是「先思后看」的边界。
 *
 * @param caseId     案例 ID（揭晓答案用）
 * @param title      案例标题（原文里的一、二…）
 * @param illness    案例原文（截断，够辨证即可）
 * @param exam       舌脉（来自 case_record.syndrome_text）
 * @param nodeId     所属方证单元 ID（「我也答一遍」开会话要用）
 * @param nodeTitle  所属方证单元
 * @param bookTitle  所属经典
 * @param formulaId  仅用于「我也答一遍」时开会话，题面不展示
 * @param drawnCount 盲盒已练次数（真实统计，不是本次页面里的点击次数）
 * @param avgScore   盲盒平均分，没练过为 null
 */
public record BlindboxVO(
        String caseId,
        String title,
        String illness,
        String exam,
        String nodeId,
        String nodeTitle,
        String bookTitle,
        String formulaId,
        int drawnCount,
        Integer avgScore) {
}
