package com.herbmind.contract.insight;

import java.util.List;
import java.util.Map;

/**
 * 可复现研究包（POST /api/biz/insight/research-pack）。
 * 只返回清单 + 内联数据（不落盘），由前端下载为 JSON；CSV 走 /api/biz/insight/export。
 */
public record ResearchPackVO(
        String packId,
        String generatedAt,
        String seed,
        Map<String, Object> summary,
        List<Map<String, Object>> tables,
        List<String> files,
        Map<String, Object> params) {
}
