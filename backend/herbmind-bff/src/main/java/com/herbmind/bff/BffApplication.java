package com.herbmind.bff;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.context.annotation.ComponentScan;

/**
 * herbmind-bff :8090 —— 前端唯一业务入口（/api/biz/**）。
 * 按页面聚合各 svc 的 /internal/**，统一包 R&lt;T&gt;。薄层：不写业务规则。
 */
@SpringBootApplication
@EnableFeignClients(basePackages = "com.herbmind.contract")
@ComponentScan({"com.herbmind.bff", "com.herbmind.common"})
public class BffApplication {

    public static void main(String[] args) {
        SpringApplication.run(BffApplication.class, args);
    }
}
