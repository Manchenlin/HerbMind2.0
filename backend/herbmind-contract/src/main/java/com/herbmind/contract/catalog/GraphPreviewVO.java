package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 首页「知识图谱预览」的最小数据（内容域自产，不依赖 svc-graph）。
 * 正式图由 svc-graph 提供；该结构保证域3 未就绪时首页也能渲染。
 */
public record GraphPreviewVO(List<GraphNodeVO> nodes, List<GraphEdgeVO> edges, String formulaId) {

    public record GraphNodeVO(String id, String type, String name, int level) {
    }

    public record GraphEdgeVO(String source, String target, String rel) {
    }
}
