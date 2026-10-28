package com.herbmind.bff.catalog;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.insight.CountItemVO;
import com.herbmind.contract.insight.HerbStatVO;
import com.herbmind.contract.insight.InsightClient;
import com.herbmind.contract.insight.ResearchPackVO;
import com.herbmind.contract.insight.TrendVO;

/**
 * 科研 / 统计 BFF（域1 的 insight 读接口）。
 */
@RestController
@RequestMapping("/api/biz")
public class InsightController {

    private final InsightClient insight;

    public InsightController(InsightClient insight) {
        this.insight = insight;
    }

    @GetMapping("/insight/herbs")
    public R<List<HerbStatVO>> herbs(
            @RequestParam(value = "limit", required = false, defaultValue = "20") int limit,
            @RequestParam(value = "bookId", required = false) String bookId) {
        return R.ok(insight.herbs(limit, bookId == null ? "" : bookId));
    }

    @GetMapping("/insight/syndrome")
    public R<List<CountItemVO>> syndrome(
            @RequestParam(value = "limit", required = false, defaultValue = "12") int limit) {
        return R.ok(insight.syndrome(limit));
    }

    @GetMapping("/insight/trend")
    public R<TrendVO> trend() {
        return R.ok(insight.trend());
    }

    /** 导出 csv / json；直接回文件流（不走 R 外壳，浏览器按下载处理）。 */
    @GetMapping("/insight/export")
    public ResponseEntity<byte[]> export(
            @RequestParam(value = "format", required = false, defaultValue = "csv") String format,
            @RequestParam(value = "kind", required = false, defaultValue = "herbs") String kind) {
        byte[] body = insight.export(format, kind);
        String ext = "json".equalsIgnoreCase(format) ? "json" : "csv";
        String contentType = "json".equals(ext) ? "application/json;charset=UTF-8" : "text/csv;charset=UTF-8";
        String filename = "herbmind-" + kind + "-" + java.time.LocalDate.now() + "." + ext;
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, contentType)
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .body(body);
    }

    @PostMapping("/insight/research-pack")
    public R<ResearchPackVO> researchPack(@RequestBody(required = false) Map<String, Object> params) {
        return R.ok(insight.researchPack(params));
    }
}
