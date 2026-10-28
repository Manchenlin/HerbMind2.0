package com.herbmind.contract.insight;

/**
 * 用药频次（GET /api/biz/insight/herbs）。
 * ratio = formulaCount / 有方剂的方剂总数。
 */
public record HerbStatVO(
        String herb,
        long count,
        long formulaCount,
        double ratio) {
}
