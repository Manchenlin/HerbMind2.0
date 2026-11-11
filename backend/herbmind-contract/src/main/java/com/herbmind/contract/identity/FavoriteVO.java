package com.herbmind.contract.identity;

import java.util.List;

/**
 * 收藏夹（GET /api/biz/me/favorites）。
 *
 * ★ 收藏是**跨域**的：方剂/医案/条文分属内容域的表，但"谁收藏了什么"属于用户域。
 *   BFF 不做跨库 JOIN —— 标题解析放在 svc-identity 的一条 SQL 里（同库，可以直接 JOIN），
 *   这样前端拿到的就是能直接点开的条目，不用自己按 targetType 再发三次请求。
 *
 * @param targetLabel 中文类型名（方剂 / 医案 / 条文），前端直接显示，不做映射
 * @param link        前端路由（/formula/f_1、/case/cs_54、/quote/q_1）
 */
public record FavoriteVO(List<Item> items, int total) {

    public record Item(
            long id,
            String targetType,
            String targetLabel,
            String targetId,
            String title,
            String subtitle,
            String link,
            String createdLabel) {
    }
}
