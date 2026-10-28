package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 单条条文（从 classic_quote.content 里按「1.xxx(35)」格式拆分出来的一条）。
 */
public record QuoteItemVO(
        String no,
        String text,
        String label,
        List<LinkVO> formulas,
        List<LinkVO> cases) {
}
