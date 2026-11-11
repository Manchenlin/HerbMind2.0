package com.herbmind.contract.training;

import java.util.List;

/**
 * 评分结果（POST /api/biz/train/answer 的响应），对齐契约 13.2 的 AnswerScoreVO。
 *
 * ★ 关于 scoredBy：契约规定的评分由 Agent 做语义评分（B5）。
 *   在 Agent 未接入前，本服务用**确定性规则**先跑通链路：
 *   - formulaScore：药味集合比对（F1），可靠
 *   - syndromeScore / treatmentScore：关键词覆盖率，只作参考
 *   前端据此在报告页标注「规则评分」，不能让人误以为是语义评分。
 */
public class AnswerScoreVO {

    private String answerId;

    /** 0-100 总分 */
    private Integer total;

    private Integer syndromeScore;

    private Integer formulaScore;

    private Integer treatmentScore;

    /** 命中项 */
    private List<String> hit;

    /** 遗漏项 */
    private List<String> miss;

    /** 多余项 */
    private List<String> extra;

    /** 原著对照文本（提交后才揭晓） */
    private String refText;

    /** rule / agent —— 前端据此提示评分来源 */
    private String scoredBy;

    public String getAnswerId() {
        return answerId;
    }

    public void setAnswerId(String answerId) {
        this.answerId = answerId;
    }

    public Integer getTotal() {
        return total;
    }

    public void setTotal(Integer total) {
        this.total = total;
    }

    public Integer getSyndromeScore() {
        return syndromeScore;
    }

    public void setSyndromeScore(Integer syndromeScore) {
        this.syndromeScore = syndromeScore;
    }

    public Integer getFormulaScore() {
        return formulaScore;
    }

    public void setFormulaScore(Integer formulaScore) {
        this.formulaScore = formulaScore;
    }

    public Integer getTreatmentScore() {
        return treatmentScore;
    }

    public void setTreatmentScore(Integer treatmentScore) {
        this.treatmentScore = treatmentScore;
    }

    public List<String> getHit() {
        return hit;
    }

    public void setHit(List<String> hit) {
        this.hit = hit;
    }

    public List<String> getMiss() {
        return miss;
    }

    public void setMiss(List<String> miss) {
        this.miss = miss;
    }

    public List<String> getExtra() {
        return extra;
    }

    public void setExtra(List<String> extra) {
        this.extra = extra;
    }

    public String getRefText() {
        return refText;
    }

    public void setRefText(String refText) {
        this.refText = refText;
    }

    public String getScoredBy() {
        return scoredBy;
    }

    public void setScoredBy(String scoredBy) {
        this.scoredBy = scoredBy;
    }
}
