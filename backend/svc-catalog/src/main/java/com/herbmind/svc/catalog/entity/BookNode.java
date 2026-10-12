package com.herbmind.svc.catalog.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/**
 * book_node —— 通用目录骨架（唯一目录表，自引用树）。
 * 注意：本表无生成列；content_unit.search_tsv 这类生成列才禁止映射。
 */
@TableName("book_node")
public class BookNode {

    @TableId
    private String id;
    private String bookId;
    private String classicId;
    private String parentId;
    /** chapter / section / category / unit */
    private String nodeType;
    private String title;
    private Integer seq;
    private String pathText;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getBookId() {
        return bookId;
    }

    public void setBookId(String bookId) {
        this.bookId = bookId;
    }

    public String getClassicId() {
        return classicId;
    }

    public void setClassicId(String classicId) {
        this.classicId = classicId;
    }

    public String getParentId() {
        return parentId;
    }

    public void setParentId(String parentId) {
        this.parentId = parentId;
    }

    public String getNodeType() {
        return nodeType;
    }

    public void setNodeType(String nodeType) {
        this.nodeType = nodeType;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public Integer getSeq() {
        return seq;
    }

    public void setSeq(Integer seq) {
        this.seq = seq;
    }

    public String getPathText() {
        return pathText;
    }

    public void setPathText(String pathText) {
        this.pathText = pathText;
    }
}
