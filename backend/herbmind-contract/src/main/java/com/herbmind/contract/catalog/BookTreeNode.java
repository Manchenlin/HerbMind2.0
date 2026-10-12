package com.herbmind.contract.catalog;

import java.util.ArrayList;
import java.util.List;

/**
 * 目录节点 DTO（对应 09 契约 §13.1）。
 * Java 字段用 camelCase —— JSON 即输出 nodeType，切勿写成 node_type。
 */
public class BookTreeNode {

    private String id;
    private String title;
    /** chapter / section / category */
    private String nodeType;
    private List<BookTreeNode> children = new ArrayList<>();

    public BookTreeNode() {
    }

    public BookTreeNode(String id, String title, String nodeType, List<BookTreeNode> children) {
        this.id = id;
        this.title = title;
        this.nodeType = nodeType;
        // 无子节点返回空列表（绝不返回 null），避免前端渲染崩溃
        this.children = children == null ? new ArrayList<>() : children;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getNodeType() {
        return nodeType;
    }

    public void setNodeType(String nodeType) {
        this.nodeType = nodeType;
    }

    public List<BookTreeNode> getChildren() {
        return children;
    }

    public void setChildren(List<BookTreeNode> children) {
        this.children = children == null ? new ArrayList<>() : children;
    }
}
