package com.herbmind.svc.catalog;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * svc-catalog :8082 —— 语料/内容域（域1）。
 * 只暴露 /internal/**（不进网关）。
 */
@SpringBootApplication
@MapperScan("com.herbmind.svc.catalog.mapper")
@ComponentScan({"com.herbmind.svc.catalog", "com.herbmind.common"})
public class CatalogApplication {

    public static void main(String[] args) {
        SpringApplication.run(CatalogApplication.class, args);
    }
}
