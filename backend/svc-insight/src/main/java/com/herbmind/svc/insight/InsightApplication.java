package com.herbmind.svc.insight;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * svc-insight :8086 —— 科研统计（域1）。
 * 只暴露 /internal/**（不进网关）。
 */
@SpringBootApplication
@ComponentScan({"com.herbmind.svc.insight", "com.herbmind.common"})
public class InsightApplication {

    public static void main(String[] args) {
        SpringApplication.run(InsightApplication.class, args);
    }
}
