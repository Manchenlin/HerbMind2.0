package com.herbmind.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * herbmind-gateway :8080 —— 统一入口。
 * 路由：/api/biz/** → BFF；/api/agent/** → Agent。
 * 注意：网关是 WebFlux，不扫描 herbmind-common 的 @RestControllerAdvice。
 * JWT 鉴权与白名单（/api/biz/user/login|register、/api/agent/health）留待后续任务实现。
 */
@SpringBootApplication
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
