package com.herbmind.svc.graph.config;

import javax.sql.DataSource;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

/**
 * PG 只读数据源：药味顺序（formula_herb.seq）与药味集合 Jaccard 都在服务端算完，
 * BFF 不需要再聚合两个数据源（见 09 契约 §15.6 步骤 1 的选型）。
 *
 * 三个刻意的设计：
 * 1. **自定义 bean，不用 spring.datasource.***：本服务的 PG 是只读辅助源，
 *    不让 Boot 的自动配置把它当主库（否则 url 缺失会在启动阶段直接报错）。
 * 2. {@code initializationFailTimeout(-1)}：PG 没起来时服务照常启动，由 /formula、/map 报错，
 *    与 {@link Neo4jConfig} 的「启动探测失败不阻止启动」同一策略。
 * 3. {@code connectionInitSql} 把会话设成 {@code default_transaction_read_only=on}：
 *    从数据库层面挡住误写，比"只写 SELECT"的自觉更可靠（本服务对 PG 只读）。
 */
@Configuration
public class PgConfig {

    @Bean(name = "pgDataSource", destroyMethod = "close")
    public DataSource pgDataSource(
            @Value("${herbmind.pg.url:jdbc:postgresql://localhost:5432/herbmind}") String url,
            @Value("${herbmind.pg.username:postgres}") String username,
            @Value("${herbmind.pg.password:postgres}") String password,
            @Value("${herbmind.pg.max-pool-size:4}") int maxPoolSize) {
        HikariConfig cfg = new HikariConfig();
        cfg.setPoolName("pg-graph-ro");
        cfg.setJdbcUrl(url);
        cfg.setUsername(username);
        cfg.setPassword(password);
        // 只读查询、并发极低，池子给小值即可
        cfg.setMaximumPoolSize(Math.max(1, maxPoolSize));
        cfg.setMinimumIdle(0);
        // -1 = 不因首次连不上而抛错（连不上就等下次请求再试）
        cfg.setInitializationFailTimeout(-1);
        cfg.setConnectionInitSql("SET default_transaction_read_only = on");
        cfg.setConnectionTimeout(3000);
        return new HikariDataSource(cfg);
    }

    @Bean(name = "pgJdbcTemplate")
    public JdbcTemplate pgJdbcTemplate(DataSource pgDataSource) {
        JdbcTemplate t = new JdbcTemplate(pgDataSource);
        // 只读分析查询，结果集小（formula 245 / formula_herb 1315），限制上限防跑飞
        t.setMaxRows(20000);
        t.setQueryTimeout(5);
        return t;
    }
}
