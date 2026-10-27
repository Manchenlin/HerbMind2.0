package com.herbmind.svc.graph;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * svc-graph :8085 —— 知识图谱查询（域3）。
 *
 * 只暴露 /internal/**（不进网关）：前端不经它，BFF 转发后包 R&lt;T&gt; 才给前端。
 * 数据源：Neo4j（:Formula {id,name,syndrome,page} / :Herb {name} / COMPOSED_OF）。
 */
@SpringBootApplication
@ComponentScan({"com.herbmind.svc.graph", "com.herbmind.common"})
public class GraphApplication {

    public static void main(String[] args) {
        SpringApplication.run(GraphApplication.class, args);
    }
}
