package com.herbmind.contract.search;

import java.util.Map;

/**
 * 分面统计：类型（方剂/医案/条文） · 经典 · 语料。
 */
public record FacetsVO(
        Map<String, Long> types,
        Map<String, Long> classics,
        Map<String, Long> books) {
}
