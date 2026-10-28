package com.herbmind.svc.catalog.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/**
 * classic_quote —— 条文（一行可能包含多条编号原文，解析由 QuoteParser 负责）。
 */
@TableName("classic_quote")
public class ClassicQuote {

    @TableId
    private String id;
    private String articleNo;
    private String classicId;
    private String content;
    /** AI 白话；多数为空 */
    private String plainText;
    private String page;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getArticleNo() { return articleNo; }
    public void setArticleNo(String articleNo) { this.articleNo = articleNo; }

    public String getClassicId() { return classicId; }
    public void setClassicId(String classicId) { this.classicId = classicId; }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    public String getPlainText() { return plainText; }
    public void setPlainText(String plainText) { this.plainText = plainText; }

    public String getPage() { return page; }
    public void setPage(String page) { this.page = page; }
}
