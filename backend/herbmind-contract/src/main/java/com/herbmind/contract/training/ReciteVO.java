package com.herbmind.contract.training;

import java.util.List;

/**
 * 背诵打卡（GET /api/biz/train/recite）。
 *
 * 只说"到期了 / 还没到期"，不假装是完整 SRS 实现：
 * 目前只有 recite_record 一张表（ease / next_review_at / last_result），
 * 调度规则写在 ReciteService 里，且**完全确定性**（同样的作答得到同样的下次复习时间），
 * 否则「同一答案两次跑分一致」这条验收标准就不成立。
 */
public record ReciteVO(List<Item> items, Stats stats) {

    /**
     * @param quoteId    classic_quote.id
     * @param articleNo  条文号（有则显示）
     * @param classicName 所属经典
     * @param content    原文（默写目标）
     * @param plainText  白话（默写后对照用，可为空）
     * @param hint       起句提示：前 6 个字 + 省略号。没有提示的话，
     *                   条文号在很多数据里是空的，用户根本不知道该默哪一条。
     * @param charCount  去标点后的字数（让人知道要写多长）
     * @param due        是否今天该复习（到期或从未背过）
     * @param lastResult 上次结果：对 / 基本对 / 不对；没背过为 null
     * @param reviewLabel 下次复习：今天 / 明天 / 3 天后；没背过为 null
     */
    public record Item(
            String quoteId,
            String articleNo,
            String classicName,
            String content,
            String plainText,
            String hint,
            int charCount,
            boolean due,
            String lastResult,
            String reviewLabel) {
    }

    /**
     * @param total    该经典的条文总数（可背范围）
     * @param due      今天到期数
     * @param mastered 已背对过（last_result=对）的条数
     * @param streak   连续打卡天数（复用学习行为日期口径）
     */
    public record Stats(int total, int due, int mastered, int streak) {
    }
}
