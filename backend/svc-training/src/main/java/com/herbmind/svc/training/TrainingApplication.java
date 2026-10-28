package com.herbmind.svc.training;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * svc-training :8084 —— 练习 / 答题 / 评分 / 学习档案（域2 成长域）。
 * 只暴露 /internal/**，由 BFF 聚合成 /api/biz/**；不直接面向浏览器。
 */
@SpringBootApplication
@MapperScan("com.herbmind.svc.training.mapper")
@ComponentScan({"com.herbmind.svc.training", "com.herbmind.common"})
public class TrainingApplication {

    public static void main(String[] args) {
        SpringApplication.run(TrainingApplication.class, args);
    }
}
