package com.herbmind.contract.insight;

/**
 * 通用计数条目（证候分布 / 章节分布 / 语料分布）。
 */
public record CountItemVO(
        String key,
        String label,
        long count,
        double ratio) {
}
