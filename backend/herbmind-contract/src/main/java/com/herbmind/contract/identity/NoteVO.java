package com.herbmind.contract.identity;

import java.util.List;

/**
 * 我的笔记（GET /api/biz/me/notes）。
 *
 * 一条笔记挂在某个对象上（方剂/医案/条文），targetTitle 由后端 JOIN 出来 ——
 * 前端不该为了显示"这条笔记是写在哪个方子上"再查一次内容域。
 */
public record NoteVO(List<Item> items, int total) {

    public record Item(
            long id,
            String targetType,
            String targetLabel,
            String targetId,
            String targetTitle,
            String content,
            String link,
            String createdLabel) {
    }
}
