package com.herbmind.contract.training;

import java.util.List;

/**
 * 提交作答（POST /api/biz/train/answer），字段与 09 契约 13.2 一致。
 */
public class SubmitAnswerReq {

    private String sessionId;

    /** 用户辨证 */
    private String syndrome;

    /** 用户治法（可选） */
    private String treatment;

    /** 药味 + 剂量 */
    private List<HerbItem> prescription;

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public String getSyndrome() {
        return syndrome;
    }

    public void setSyndrome(String syndrome) {
        this.syndrome = syndrome;
    }

    public String getTreatment() {
        return treatment;
    }

    public void setTreatment(String treatment) {
        this.treatment = treatment;
    }

    public List<HerbItem> getPrescription() {
        return prescription;
    }

    public void setPrescription(List<HerbItem> prescription) {
        this.prescription = prescription;
    }

    /** 契约：HerbItem = { herb, dose, unit } */
    public static class HerbItem {

        private String herb;

        private Double dose;

        private String unit;

        public HerbItem() {
        }

        public HerbItem(String herb, Double dose, String unit) {
            this.herb = herb;
            this.dose = dose;
            this.unit = unit;
        }

        public String getHerb() {
            return herb;
        }

        public void setHerb(String herb) {
            this.herb = herb;
        }

        public Double getDose() {
            return dose;
        }

        public void setDose(Double dose) {
            this.dose = dose;
        }

        public String getUnit() {
            return unit;
        }

        public void setUnit(String unit) {
            this.unit = unit;
        }
    }
}
