package com.herbmind.contract.training;

import java.util.List;

/**
 * 盲盒揭晓（GET /api/biz/train/blindbox/{caseId}/answer）。
 *
 * 全部取自数据表（formula / formula_herb），不做任何推理 ——
 * 设计红线：只引用，不推断疗效、不给处方建议。
 *
 * @param formulaName  原著所用方
 * @param syndromeText 原著辨证（formula.syndrome_text）
 * @param efficacy     原著治法（formula.efficacy）
 * @param prescription 原著处方，形如「麻黄 9g」
 * @param refText      拼好的整段对照文本，前端直接展示
 */
public record BlindboxAnswerVO(
        String formulaName,
        String syndromeText,
        String efficacy,
        List<String> prescription,
        String refText) {
}
