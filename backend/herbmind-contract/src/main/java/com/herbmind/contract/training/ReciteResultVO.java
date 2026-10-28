package com.herbmind.contract.training;

import java.util.List;

/**
 * 背诵结果（POST /api/biz/train/recite 的响应）。
 *
 * ★ 评分是**字面比对**（去掉标点后按二元组重合度算），不是语义理解：
 *   漏一个「不」字会扣分，但写「患者不出汗」不会算对「无汗」。
 *   所以界面上必须标 level 与 matched/missed，让人看得见差在哪，而不是只给一个分数。
 *
 * @param score    0-100
 * @param level    对（>=90）/ 基本对（>=70）/ 不对
 * @param matched  命中的分句（按原文，逐个分句判断是否出现在默写里）
 * @param missed   漏掉的分句
 * @param standard 原文（对照）
 * @param nextReviewLabel 下次复习：明天 / 3 天后 / 7 天后
 * @param mastered 是否已算背熟（连对 2 次或一次全对）
 * @param scoredBy rule —— 前端据实标注「字面比对」
 */
public record ReciteResultVO(
        int score,
        String level,
        List<String> matched,
        List<String> missed,
        String standard,
        String nextReviewLabel,
        boolean mastered,
        String scoredBy) {
}
