package com.herbmind.svc.search;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * svc-search :8083 —— 检索域（域1）。
 * 只暴露 /internal/**（不进网关）；BFF 负责包 R<T>。
 */
@SpringBootApplication
@ComponentScan({"com.herbmind.svc.search", "com.herbmind.common"})
public class SearchApplication {

    public static void main(String[] args) {
        SpringApplication.run(SearchApplication.class, args);
    }
}
