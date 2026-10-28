package com.herbmind.contract.training;

import java.util.List;

/**
 * 练习题面（GET /api/biz/train/unit/{ref}）。
 *
 * ★ 必须藏答案：不返回方名、不返回功效治法。题面只给「症状 + 舌脉」，
 *   否则「先思后看」就变成抄答案了。答案在提交后由 AnswerScoreVO.refText 揭晓。
 */
public class PracticeQuestionVO {

    private String sessionId;

    /** 第几题（从 1 开始） */
    private Integer index;

    /** 本题所属节点共几题 */
    private Integer total;

    private String nodeId;

    private String nodeTitle;

    private String bookTitle;

    /** 案例 ID（前端展示「案例一」这类序号，不展示原始 title，因为它含方名） */
    private String caseId;

    /** 症状描述（来自 formula.syndrome_text） */
    private String symptoms;

    /** 舌脉（来自 case_record.syndrome_text） */
    private String signs;

    /** 审题提示：由症状里挑关键词生成，不含答案 */
    private String hint;

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public Integer getIndex() {
        return index;
    }

    public void setIndex(Integer index) {
        this.index = index;
    }

    public Integer getTotal() {
        return total;
    }

    public void setTotal(Integer total) {
        this.total = total;
    }

    public String getNodeId() {
        return nodeId;
    }

    public void setNodeId(String nodeId) {
        this.nodeId = nodeId;
    }

    public String getNodeTitle() {
        return nodeTitle;
    }

    public void setNodeTitle(String nodeTitle) {
        this.nodeTitle = nodeTitle;
    }

    public String getBookTitle() {
        return bookTitle;
    }

    public void setBookTitle(String bookTitle) {
        this.bookTitle = bookTitle;
    }

    public String getCaseId() {
        return caseId;
    }

    public void setCaseId(String caseId) {
        this.caseId = caseId;
    }

    public String getSymptoms() {
        return symptoms;
    }

    public void setSymptoms(String symptoms) {
        this.symptoms = symptoms;
    }

    public String getSigns() {
        return signs;
    }

    public void setSigns(String signs) {
        this.signs = signs;
    }

    public String getHint() {
        return hint;
    }

    public void setHint(String hint) {
        this.hint = hint;
    }
}
