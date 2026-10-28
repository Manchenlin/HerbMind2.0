package com.herbmind.svc.catalog.entity;

import java.math.BigDecimal;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/** formula_herb —— 方剂药味明细（君臣佐使）。 */
@TableName("formula_herb")
public class FormulaHerb {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String formulaId;
    private String herbName;
    private BigDecimal dose;
    private String unit;
    /** 君 / 臣 / 佐 / 使，可空 */
    private String role;
    private Integer seq;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getFormulaId() { return formulaId; }
    public void setFormulaId(String formulaId) { this.formulaId = formulaId; }

    public String getHerbName() { return herbName; }
    public void setHerbName(String herbName) { this.herbName = herbName; }

    public BigDecimal getDose() { return dose; }
    public void setDose(BigDecimal dose) { this.dose = dose; }

    public String getUnit() { return unit; }
    public void setUnit(String unit) { this.unit = unit; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public Integer getSeq() { return seq; }
    public void setSeq(Integer seq) { this.seq = seq; }
}
