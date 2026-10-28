package com.herbmind.contract.insight;

import java.util.List;
import java.util.Map;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * svc-insight 内部契约（:8086）。返回裸 DTO，由 BFF 包 R。
 */
@FeignClient(name = "svc-insight", path = "/internal/insight",
        url = "${herbmind.svc-insight-url:http://localhost:8086}")
public interface InsightClient {

    @GetMapping("/herbs")
    List<HerbStatVO> herbs(@RequestParam(value = "limit", defaultValue = "20") int limit,
                          @RequestParam(value = "bookId", required = false) String bookId);

    @GetMapping("/syndrome")
    List<CountItemVO> syndrome(@RequestParam(value = "limit", defaultValue = "12") int limit);

    @GetMapping("/trend")
    TrendVO trend();

    /** csv / json */
    @GetMapping("/export")
    byte[] export(@RequestParam("format") String format,
                  @RequestParam("kind") String kind);

    @PostMapping("/research-pack")
    ResearchPackVO researchPack(@RequestBody Map<String, Object> params);
}
