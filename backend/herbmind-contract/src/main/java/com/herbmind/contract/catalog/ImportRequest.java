package com.herbmind.contract.catalog;

/**
 * 导入语料请求（UGC）—— 对应 POST /api/biz/catalog/import。
 * 阶段 M2 只落库 + 建治理工单；真正的解析 / 向量化在后续版本由 ETL 完成。
 */
public record ImportRequest(
        String title,
        String bookType,
        String author,
        String dynasty,
        String sourceLicense,
        String visibility,
        Boolean generateEmbedding,
        Boolean extractHerbs,
        String note) {
}
