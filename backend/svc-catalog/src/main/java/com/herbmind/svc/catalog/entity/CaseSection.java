package com.herbmind.svc.catalog.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/** case_section —— 医案栏目（案例原文 / 按语 …）。 */
@TableName("case_section")
public class CaseSection {

    @TableId
    private String id;
    private String caseId;
    private String kind;
    private String content;
    private Integer seq;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getCaseId() { return caseId; }
    public void setCaseId(String caseId) { this.caseId = caseId; }

    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public Integer getSeq() { return seq; }
    public void setSeq(Integer seq) { this.seq = seq; }
}
