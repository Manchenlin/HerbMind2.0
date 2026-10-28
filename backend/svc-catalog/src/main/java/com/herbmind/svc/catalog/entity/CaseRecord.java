package com.herbmind.svc.catalog.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/**
 * case_record —— 医案主体。
 * 注意：symptoms_jsonb / signs_jsonb 是 JSONB，本实体**不映射**（避免 PGobject 转换问题），
 * 需要时由 service 单独查。
 */
@TableName("case_record")
public class CaseRecord {

    @TableId
    private String id;
    private String title;
    private String unitType;
    private String sourceFormula;
    private String mainFormulaId;
    private String syndromeText;
    private String page;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getUnitType() { return unitType; }
    public void setUnitType(String unitType) { this.unitType = unitType; }

    public String getSourceFormula() { return sourceFormula; }
    public void setSourceFormula(String sourceFormula) { this.sourceFormula = sourceFormula; }

    public String getMainFormulaId() { return mainFormulaId; }
    public void setMainFormulaId(String mainFormulaId) { this.mainFormulaId = mainFormulaId; }

    public String getSyndromeText() { return syndromeText; }
    public void setSyndromeText(String syndromeText) { this.syndromeText = syndromeText; }

    public String getPage() { return page; }
    public void setPage(String page) { this.page = page; }
}
