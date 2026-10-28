package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 医案详情页数据 —— 对应 GET /api/biz/case/{id}/page。
 * siblings 为「同一主方下的其它医案」，前端用于「案例一 / 二 / 三」切换（09 §2、02 §M2）。
 */
public record CaseVO(
        String id,
        String title,
        String unitType,
        String mainFormulaId,
        String mainFormulaName,
        String syndrome,
        String page,
        String bookId,
        String bookTitle,
        String chapter,
        List<CaseSectionVO> sections,
        List<QuoteRefVO> quotes,
        List<CaseBriefVO> siblings) {
}
