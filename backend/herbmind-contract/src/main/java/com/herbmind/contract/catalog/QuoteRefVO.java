package com.herbmind.contract.catalog;

/**
 * 条文摘要（列表 / 引用卡用）。label 形如「《伤寒论》第 35 条」。
 */
public record QuoteRefVO(
        String id,
        String articleNo,
        String classicName,
        String content,
        String plainText,
        String page,
        String label) {
}
