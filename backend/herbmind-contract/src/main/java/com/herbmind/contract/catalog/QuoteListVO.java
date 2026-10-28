package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 条文列表（分页）—— 对应 GET /api/biz/quote/list（17 号手册 A1 的 `/quote/list`）。
 * 列表项用 QuoteRefVO（id / 条号 / 经典 / 摘录 / 页码 / 展示标题）。
 */
public record QuoteListVO(
        List<QuoteRefVO> list,
        long total,
        int page,
        int size) {
}
