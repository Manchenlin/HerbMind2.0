package com.herbmind.contract.training;

import java.util.List;

/**
 * 评分报告（GET /api/biz/train/report/{answerId}）。
 *
 * 一条答题记录的全貌：题面来源 + 我的作答 + 分项 + 逐项比对 + 原著对照。
 *
 * ★ radar 是**累计能力画像**（与「我的·总览」同一口径），不是这一次答题的雷达。
 *   单题只有三个分项，硬凑五维雷达就是编数据 —— 所以界面上要写清是「累计」。
 *
 * @param userPrescription 我提交的药味（"麻黄 9g" 形式）
 */
public record MeReportVO(
        String answerId,
        String sessionId,
        String nodeTitle,
        String bookTitle,
        String formulaName,
        String caseId,
        String submittedLabel,
        int durationSeconds,
        int total,
        int syndromeScore,
        int formulaScore,
        int treatmentScore,
        List<String> hit,
        List<String> miss,
        List<String> extra,
        String refText,
        String userSyndrome,
        String userTreatment,
        List<String> userPrescription,
        String scoredBy,
        List<Radar> radar) {

    public record Radar(String key, String label, int value) {
    }
}
