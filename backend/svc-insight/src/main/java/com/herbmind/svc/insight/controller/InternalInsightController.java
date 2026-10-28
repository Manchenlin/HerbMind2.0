package com.herbmind.svc.insight.controller;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.contract.insight.CountItemVO;
import com.herbmind.contract.insight.HerbStatVO;
import com.herbmind.contract.insight.ResearchPackVO;
import com.herbmind.contract.insight.TrendVO;
import com.herbmind.svc.insight.service.InsightService;

/**
 * 内部科研统计接口（/internal/insight/**，不进网关）。
 */
@RestController
@RequestMapping("/internal/insight")
public class InternalInsightController {

    private final InsightService service;

    public InternalInsightController(InsightService service) {
        this.service = service;
    }

    @GetMapping("/herbs")
    public List<HerbStatVO> herbs(
            @RequestParam(value = "limit", required = false, defaultValue = "20") int limit,
            @RequestParam(value = "bookId", required = false) String bookId) {
        return service.herbs(limit, bookId);
    }

    /** 供 Agent 的 get_herb_stats 工具复用（语义同 /herbs）。 */
    @GetMapping("/herb-stats")
    public List<HerbStatVO> herbStats(
            @RequestParam(value = "limit", required = false, defaultValue = "20") int limit,
            @RequestParam(value = "bookId", required = false) String bookId) {
        return service.herbs(limit, bookId);
    }

    @GetMapping("/syndrome")
    public List<CountItemVO> syndrome(
            @RequestParam(value = "limit", required = false, defaultValue = "12") int limit) {
        return service.syndrome(limit);
    }

    @GetMapping("/trend")
    public TrendVO trend() {
        return service.trend();
    }

    @GetMapping("/export")
    public ResponseEntity<byte[]> export(
            @RequestParam(value = "format", required = false, defaultValue = "csv") String format,
            @RequestParam(value = "kind", required = false, defaultValue = "herbs") String kind) {
        byte[] body = service.export(format, kind);
        String ext = "json".equalsIgnoreCase(format) ? "json" : "csv";
        String contentType = "json".equals(ext) ? "application/json;charset=UTF-8" : "text/csv;charset=UTF-8";
        String filename = "herbmind-" + kind + "-" + java.time.LocalDate.now() + "." + ext;
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, contentType)
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                .body(body);
    }

    @PostMapping("/research-pack")
    public ResearchPackVO researchPack(@RequestBody(required = false) Map<String, Object> params) {
        return service.researchPack(params);
    }

    /** 备用：直接返回 UTF-8 文本（便于 curl / 调试）。 */
    @GetMapping(value = "/export/text", produces = MediaType.TEXT_PLAIN_VALUE)
    public String exportText(
            @RequestParam(value = "format", required = false, defaultValue = "csv") String format,
            @RequestParam(value = "kind", required = false, defaultValue = "herbs") String kind) {
        return new String(service.export(format, kind), StandardCharsets.UTF_8);
    }
}
