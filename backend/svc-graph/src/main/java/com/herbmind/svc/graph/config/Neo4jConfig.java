package com.herbmind.svc.graph.config;

import org.neo4j.driver.AuthTokens;
import org.neo4j.driver.Driver;
import org.neo4j.driver.GraphDatabase;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Neo4j 连接。
 *
 * 两个刻意的设计：
 * 1. Driver 是**线程安全且昂贵**的对象，全应用只建一个（自带连接池），用 destroyMethod 关。
 * 2. 启动时只做一次连通性探测并打日志，**失败不阻止启动**——Neo4j 没起来时
 *    服务照样能起，由 /neighbors 报错，而不是整个进程起不来（与 agent 侧同一策略）。
 */
@Configuration
public class Neo4jConfig {

    private static final Logger log = LoggerFactory.getLogger(Neo4jConfig.class);

    @Bean(destroyMethod = "close")
    public Driver neo4jDriver(
            @Value("${neo4j.uri:bolt://localhost:7687}") String uri,
            @Value("${neo4j.username:neo4j}") String username,
            @Value("${neo4j.password}") String password) {
        log.info("创建 Neo4j Driver：{}", uri);
        return GraphDatabase.driver(uri, AuthTokens.basic(username, password));
    }

    @Bean
    public ApplicationRunner neo4jWarmup(Driver driver) {
        return args -> {
            try (var session = driver.session()) {
                long formulas = session.run("MATCH (f:Formula) RETURN count(f) AS c")
                        .single().get("c").asLong();
                long herbs = session.run("MATCH (h:Herb) RETURN count(h) AS c")
                        .single().get("c").asLong();
                log.info("Neo4j 连接正常：Formula={} Herb={}", formulas, herbs);
            } catch (Exception e) {
                log.warn("Neo4j 暂时不可用（服务仍启动，/neighbors 会返回错误）：{}", e.getMessage());
            }
        };
    }
}
