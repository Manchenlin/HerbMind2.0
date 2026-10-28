package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 方剂摘要（目录节点 / 搜索结果 / 相关方 用）。
 */
public record FormulaBriefVO(
        String id,
        String name,
        String efficacy,
        String syndrome,
        String page,
        String nodeId,
        String nodeTitle,
        List<HerbVO> herbs) {
}
