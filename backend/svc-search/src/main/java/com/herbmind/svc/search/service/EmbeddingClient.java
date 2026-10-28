package com.herbmind.svc.search.service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * 查询向量客户端（bge-m3 / OpenAI 兼容接口，如硅基流动 SiliconFlow）。
 *
 * - 未配置 url、调用失败、维度不符 → 返回 null，检索自动降级（不抛异常）。
 * - 只对**查询**做 embedding；语料向量由 ETL 一次性产出（见 10 号文档）。
 */
@Component
public class EmbeddingClient {

    private static final Logger log = LoggerFactory.getLogger(EmbeddingClient.class);

    private final String url;
    private final String apiKey;
    private final String model;
    private final int dimension;
    private final RestClient http;

    public EmbeddingClient(
            @Value("${herbmind.embedding.url:}") String url,
            @Value("${herbmind.embedding.api-key:}") String apiKey,
            @Value("${herbmind.embedding.model:BAAI/bge-m3}") String model,
            @Value("${herbmind.embedding.dimension:1024}") int dimension,
            @Value("${herbmind.embedding.connect-timeout-ms:800}") int connectTimeoutMs,
            @Value("${herbmind.embedding.read-timeout-ms:2500}") int readTimeoutMs) {
        this.url = url == null ? "" : url.trim();
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.model = model;
        this.dimension = dimension;

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(connectTimeoutMs));
        factory.setReadTimeout(Duration.ofMillis(readTimeoutMs));
        this.http = RestClient.builder().requestFactory(factory).build();
    }

    public boolean enabled() {
        return !url.isEmpty();
    }

    /** 失败返回 null（检索降级，而不是 5xx）。 */
    @SuppressWarnings("unchecked")
    public float[] embed(String text) {
        if (!enabled() || text == null || text.isBlank()) {
            return null;
        }
        try {
            Map<String, Object> body = Map.of(
                    "model", model,
                    "input", List.of(text));
            Map<String, Object> resp = http.post()
                    .uri(url)
                    .header("Content-Type", "application/json")
                    .headers(h -> {
                        if (!apiKey.isEmpty()) {
                            h.setBearerAuth(apiKey);
                        }
                    })
                    .body(body)
                    .retrieve()
                    .body(Map.class);

            if (resp == null) {
                return null;
            }
            Object data = resp.get("data");
            if (!(data instanceof List<?> list) || list.isEmpty()) {
                log.warn("embedding 响应缺少 data 字段");
                return null;
            }
            Object first = list.get(0);
            if (!(first instanceof Map<?, ?> m)) {
                return null;
            }
            Object emb = m.get("embedding");
            if (!(emb instanceof List<?> nums) || nums.size() != dimension) {
                log.warn("embedding 维度不符：期望 {}，实际 {}", dimension,
                        emb instanceof List<?> l ? l.size() : "null");
                return null;
            }
            float[] out = new float[nums.size()];
            for (int i = 0; i < out.length; i++) {
                out[i] = ((Number) nums.get(i)).floatValue();
            }
            return out;
        } catch (Exception e) {
            log.warn("查询向量生成失败，检索降级为词项/全文召回：{}", e.getMessage());
            return null;
        }
    }

    /** 向量字面量（服务端生成，数字已校验，直接拼进 SQL 避免 JDBC 的 vector 类型转换坑）。 */
    public static String toLiteral(float[] v) {
        if (v == null || v.length == 0) {
            return null;
        }
        StringBuilder sb = new StringBuilder(v.length * 10).append('[');
        List<String> parts = new ArrayList<>(v.length);
        for (float f : v) {
            if (Float.isNaN(f) || Float.isInfinite(f)) {
                return null;
            }
            parts.add(String.format(java.util.Locale.ROOT, "%.6f", f));
        }
        sb.append(String.join(",", parts)).append(']');
        return sb.toString();
    }
}
