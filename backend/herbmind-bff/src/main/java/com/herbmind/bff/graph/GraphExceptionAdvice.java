package com.herbmind.bff.graph;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herbmind.common.R;

import feign.FeignException;

/**
 * 图谱接口的 Feign 异常 → 统一 R 外壳（<b>只作用于 {@link GraphController}</b>）。
 *
 * <p><b>为什么必须单独写这一层</b>：herbmind-common 的 {@code GlobalExceptionHandler} 只有
 * 「IllegalArgumentException → 4000」和「其它 → 5000」两条分支。svc-graph 返回的
 * 4040（实体不存在）到了 BFF 会以 {@link FeignException} 形式抛出，被兜底成 <b>5000</b> ——
 * 于是前端把「这本书里没有这首方」误报成「图谱服务异常」，提示完全跑偏。
 *
 * <p>不改 common 的全局 handler：那是横切资产（改动要三人 review），而且改它会顺带影响
 * catalog / training 等既有端点的错误语义。用 {@code assignableTypes} 把爆炸半径限制在
 * 图谱控制器内。
 *
 * <p>状态码映射遵循 09 契约 §0.1「HTTP 状态码同时正确」：
 * <ul>
 *   <li>400 → 400 / 4000 参数错误（label 不支持、hops 越界、方名重名需改用 ID）</li>
 *   <li>404 → 404 / 4040 实体不存在</li>
 *   <li>无响应（连接失败/超时，Feign 的 status 为 -1）→ 503 / 5030</li>
 *   <li>其它 → 原样透传状态码，code 5000</li>
 * </ul>
 */
@RestControllerAdvice(assignableTypes = GraphController.class)
@Order(Ordered.HIGHEST_PRECEDENCE)
public class GraphExceptionAdvice {

    private static final Logger log = LoggerFactory.getLogger(GraphExceptionAdvice.class);

    private final ObjectMapper objectMapper;

    public GraphExceptionAdvice(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @ExceptionHandler(FeignException.class)
    public ResponseEntity<R<Void>> handleFeign(FeignException e) {
        int status = e.status();

        // status == -1：请求没到服务端（svc-graph 没起、端口不通、读超时）
        if (status <= 0) {
            log.warn("svc-graph 不可达：{}", e.getMessage());
            return build(HttpStatus.SERVICE_UNAVAILABLE, 5030,
                    "图谱服务不可用：请确认 svc-graph(8085) 已启动");
        }

        String upstreamMsg = extractMsg(e);

        if (status == HttpStatus.BAD_REQUEST.value()) {
            log.warn("图谱参数错误：{}", upstreamMsg);
            return build(HttpStatus.BAD_REQUEST, 4000, upstreamMsg == null ? "参数不合法" : upstreamMsg);
        }

        if (status == HttpStatus.NOT_FOUND.value()) {
            log.info("图谱实体不存在：{}", upstreamMsg);
            return build(HttpStatus.NOT_FOUND, 4040, upstreamMsg == null ? "实体不存在" : upstreamMsg);
        }

        // 其余（主要是 500：Neo4j / PG 不可用）原样透传，让前端能照 status 给出针对性提示。
        // 必须用 resolve()：valueOf() 对非标准码（499/599 等）会抛 IllegalArgumentException，
        // 那会绕过本 advice 直接变成裸 500（连 R 外壳都没有），前端反而拿不到 msg。
        HttpStatus mapped = HttpStatus.resolve(status);
        if (mapped == null) {
            log.error("svc-graph 返回无法映射的状态码 {}：{}", status, upstreamMsg);
            return build(HttpStatus.BAD_GATEWAY, 5000,
                    upstreamMsg == null ? "图谱服务异常（上游返回未知状态码）" : upstreamMsg);
        }
        log.error("svc-graph 返回 {}：{}", status, upstreamMsg);
        return build(mapped, 5000, upstreamMsg == null ? "图谱服务异常" : upstreamMsg);
    }

    private ResponseEntity<R<Void>> build(HttpStatus status, int code, String msg) {
        return ResponseEntity.status(status).body(R.fail(code, msg));
    }

    /**
     * 从 svc-graph 的错误响应体里取 {@code R.msg}。
     *
     * <p>svc-graph 的错误都是 R 外壳（{@code {"code":4040,"msg":"..."}}）。取不到就返回 null，
     * 由调用方给默认文案 —— 不把原始 JSON 或堆栈直接甩给前端。
     */
    private String extractMsg(FeignException e) {
        String body = e.contentUTF8();
        if (body == null || body.isBlank()) {
            return null;
        }
        try {
            JsonNode node = objectMapper.readTree(body);
            JsonNode msg = node.get("msg");
            if (msg != null && !msg.isNull() && !msg.asText().isBlank()) {
                return msg.asText();
            }
        } catch (Exception ignored) {
            // 响应体不是 JSON（网关错误页等）：走调用方的默认文案
        }
        return null;
    }
}
