package com.herbmind.contract.identity;

import java.util.List;

/**
 * 讨论区（GET /api/biz/discuss）。
 *
 * 表结构是「话题（discuss_topic）+ 楼层（discuss_floor）」两级。
 * 列表带上每个话题最新的若干层，一次请求就能渲染出原型里那种"话题卡 + 两三条回复"的样子。
 *
 * @param author 昵称（取不到就显示"匿名"，绝不显示 user_id）
 */
public record DiscussVO(List<Topic> topics, int total) {

    public record Topic(
            String id,
            String title,
            String targetType,
            String targetId,
            String author,
            String createdLabel,
            boolean pinned,
            int floorCount,
            List<Floor> floors) {
    }

    /**
     * @param isPinned 楼层被加精（原型里的「已被加精」徽条）
     */
    public record Floor(
            String id,
            String author,
            String content,
            String createdLabel,
            boolean isPinned) {
    }
}
