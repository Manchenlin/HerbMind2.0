package com.herbmind.contract.identity;

/**
 * 写笔记 / 发话题 / 回帖 / 加收藏的请求体（都是小表单，合并在一个文件里便于对照）。
 *
 * targetType 只允许 formula / case / quote（与 user_favorite 的注释一致）；
 * 传别的值会被服务层拒掉 —— 前端不该靠拼字符串试探。
 */
public final class UserContentReq {

    private UserContentReq() {
    }

    /** 加收藏 / 取消收藏 */
    public record Favorite(String targetType, String targetId) {
    }

    /** 新建笔记；id 为空表示新建，非空表示改写 */
    public record Note(Long id, String targetType, String targetId, String content) {
    }

    /** 发话题：标题 + 首楼内容 */
    public record Topic(String targetType, String targetId, String title, String content) {
    }

    /** 回帖 */
    public record Floor(String content) {
    }
}
