package com.herbmind.svc.catalog.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/** formula —— 方剂（方证单元）。 */
@TableName("formula")
public class Formula {

    @TableId
    private String id;
    private String name;
    private String pinyin;
    private String alias;
    private String efficacy;
    private String syndromeText;
    private String sourceText;
    private String page;
    /** 所属目录分类节点（book_node.id） */
    private String nodeId;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getPinyin() { return pinyin; }
    public void setPinyin(String pinyin) { this.pinyin = pinyin; }

    public String getAlias() { return alias; }
    public void setAlias(String alias) { this.alias = alias; }

    public String getEfficacy() { return efficacy; }
    public void setEfficacy(String efficacy) { this.efficacy = efficacy; }

    public String getSyndromeText() { return syndromeText; }
    public void setSyndromeText(String syndromeText) { this.syndromeText = syndromeText; }

    public String getSourceText() { return sourceText; }
    public void setSourceText(String sourceText) { this.sourceText = sourceText; }

    public String getPage() { return page; }
    public void setPage(String page) { this.page = page; }

    public String getNodeId() { return nodeId; }
    public void setNodeId(String nodeId) { this.nodeId = nodeId; }
}
