package com.herbmind.gateway.filter;

import java.nio.charset.StandardCharsets;
import java.util.List;

import javax.crypto.SecretKey;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import reactor.core.publisher.Mono;

/**
 * 网关统一鉴权（09 契约 §0）。
 *
 * 职责只有两件：
 * 1. 校验 Authorization: Bearer &lt;token&gt;，非法直接 401（前端拦截器据此跳登录页）；
 * 2. 把 token 里的 sub（userId）与 role 注入成 X-User-Id / X-User-Role 传给下游。
 *
 * 下游（BFF / svc-*）因此**不需要再解析 JWT**，只读请求头即可。
 * 客户端自带的 X-User-Id 会被强制覆盖，防止伪造身份。
 *
 * 白名单：登录、注册、Agent 健康检查。
 */
@Component
public class JwtAuthGatewayFilter implements GlobalFilter, Ordered {

    /** 无需登录即可访问的路径（精确匹配）。 */
    private static final List<String> WHITELIST = List.of(
            "/api/biz/user/login",
            "/api/biz/user/register",
            "/api/agent/health"
    );

    private static final String USER_ID_HEADER = "X-User-Id";
    private static final String USER_ROLE_HEADER = "X-User-Role";

    private final SecretKey key;

    public JwtAuthGatewayFilter(
            @Value("${herbmind.jwt.secret}") String secret) {
        // 与 svc-identity 使用同一密钥（HS256 要求 >= 32 字节）
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getURI().getPath();

        // 非业务接口（如 actuator）与白名单直接放行
        if (!path.startsWith("/api/") || WHITELIST.contains(path)) {
            return chain.filter(exchange);
        }

        String auth = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (auth == null || !auth.startsWith("Bearer ")) {
            return unauthorized(exchange, "未登录或登录已过期，请先登录");
        }

        Claims claims;
        try {
            claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(auth.substring(7))
                    .getPayload();
        } catch (RuntimeException e) {
            return unauthorized(exchange, "登录已过期，请重新登录");
        }

        String userId = claims.getSubject();
        if (userId == null || userId.isBlank()) {
            return unauthorized(exchange, "登录信息异常，请重新登录");
        }
        Object role = claims.get("role");

        ServerHttpRequest mutated = exchange.getRequest().mutate()
                .headers(h -> {
                    h.remove(USER_ID_HEADER);              // 覆盖客户端伪造值
                    h.set(USER_ID_HEADER, userId);
                    if (role != null) {
                        h.set(USER_ROLE_HEADER, String.valueOf(role));
                    }
                })
                .build();

        return chain.filter(exchange.mutate().request(mutated).build());
    }

    /** 401 也要是 R 结构，前端拦截器才认得出是登录态问题。 */
    private Mono<Void> unauthorized(ServerWebExchange exchange, String msg) {
        exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = "{\"code\":401,\"msg\":\"" + msg + "\",\"data\":null}";
        DataBuffer buf = exchange.getResponse().bufferFactory()
                .wrap(body.getBytes(StandardCharsets.UTF_8));
        return exchange.getResponse().writeWith(Mono.just(buf));
    }

    @Override
    public int getOrder() {
        // 早于路由转发执行
        return -100;
    }
}
