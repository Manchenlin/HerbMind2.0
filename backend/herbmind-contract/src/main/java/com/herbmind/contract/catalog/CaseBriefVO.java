package com.herbmind.contract.catalog;

/**
 * 医案摘要（方剂页 / 目录节点 用）。
 */
public record CaseBriefVO(
        String id,
        String title,
        String mainFormulaId,
        String mainFormulaName,
        String syndrome,
        String page) {
}
