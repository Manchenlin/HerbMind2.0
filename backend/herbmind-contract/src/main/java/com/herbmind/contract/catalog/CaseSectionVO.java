package com.herbmind.contract.catalog;

/**
 * 医案栏目（案例原文 / 按语 …），content 保留原始换行。
 */
public record CaseSectionVO(String id, String kind, String content, int seq) {
}
