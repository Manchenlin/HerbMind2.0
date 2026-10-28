package com.herbmind.svc.catalog.entity;

import java.time.OffsetDateTime;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/** book —— 语料注册表（插拔式书架）。 */
@TableName("book")
public class Book {

    @TableId
    private String id;
    private String title;
    /** fz / bencao / drug / case */
    private String bookType;
    private String author;
    private String dynasty;
    private String edition;
    private String sourceLicense;
    /** draft / 已发布 / 整理中 … */
    private String ingestStatus;
    private OffsetDateTime createdAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getBookType() { return bookType; }
    public void setBookType(String bookType) { this.bookType = bookType; }

    public String getAuthor() { return author; }
    public void setAuthor(String author) { this.author = author; }

    public String getDynasty() { return dynasty; }
    public void setDynasty(String dynasty) { this.dynasty = dynasty; }

    public String getEdition() { return edition; }
    public void setEdition(String edition) { this.edition = edition; }

    public String getSourceLicense() { return sourceLicense; }
    public void setSourceLicense(String sourceLicense) { this.sourceLicense = sourceLicense; }

    public String getIngestStatus() { return ingestStatus; }
    public void setIngestStatus(String ingestStatus) { this.ingestStatus = ingestStatus; }

    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }
}
