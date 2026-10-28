package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 目录节点详情 —— 对应 GET /api/biz/catalog/node/{id}。
 * 含面包屑、子节点，以及该节点（含所有后代节点）下的方剂 / 医案 / 条文。
 */
public record NodeDetailVO(
        BookTreeNode node,
        String bookId,
        String bookTitle,
        String classicId,
        String parentId,
        String pathText,
        List<LinkVO> breadcrumb,
        List<FormulaBriefVO> formulas,
        List<CaseBriefVO> cases,
        List<QuoteRefVO> quotes,
        int childCount) {
}
