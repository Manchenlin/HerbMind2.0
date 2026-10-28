package com.herbmind.svc.identity;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * svc-identity :8081 —— 成长域：用户 / 认证（域2）。
 * 只暴露 /internal/**（不进网关）。
 */
@SpringBootApplication
@MapperScan("com.herbmind.svc.identity.mapper")
@ComponentScan({"com.herbmind.svc.identity", "com.herbmind.common"})
public class IdentityApplication {

    public static void main(String[] args) {
        SpringApplication.run(IdentityApplication.class, args);
    }
}
