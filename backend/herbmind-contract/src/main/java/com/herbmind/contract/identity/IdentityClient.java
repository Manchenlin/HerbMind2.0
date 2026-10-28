package com.herbmind.contract.identity;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * svc-identity 内部契约（OpenFeign 4.x：禁类级 @RequestMapping，用 path 属性）。
 *
 * /internal/** 返回**裸 DTO**（不包 R），由 BFF 统一包 R 给前端。
 * url 默认本地直连 :8081；上 Nacos 后用 herbmind.svc-identity-url 覆盖。
 *
 * 收藏 / 笔记 / 讨论都放这里：它们的表（user_favorite / user_note / discuss_*）
 * 属于用户域，和 app_user 同库，标题解析可以在一条 SQL 里 JOIN 完。
 * 放 svc-training 会变成跨服务的伪关联 —— 明明同库，却要两次调用再拼。
 */
@FeignClient(name = "svc-identity", path = "/internal/identity",
        url = "${herbmind.svc-identity-url:http://localhost:8081}")
public interface IdentityClient {

    @PostMapping("/user/register")
    LoginResp register(@RequestBody RegisterReq req);

    @PostMapping("/user/login")
    LoginResp login(@RequestBody LoginReq req);

    /** 当前用户：用户上下文由网关注入 X-User-Id（BFF 需透传该头）。 */
    @GetMapping("/user/me")
    UserDto me(@RequestHeader("X-User-Id") String userId);

    /* -------------------------------- 收藏夹 -------------------------------- */

    @GetMapping("/favorites")
    FavoriteVO favorites(@RequestParam("userId") String userId);

    @PostMapping("/favorites")
    FavoriteVO addFavorite(@RequestParam("userId") String userId,
                           @RequestBody UserContentReq.Favorite req);

    @DeleteMapping("/favorites/{id}")
    FavoriteVO removeFavorite(@RequestParam("userId") String userId,
                              @PathVariable("id") long id);

    /* -------------------------------- 我的笔记 -------------------------------- */

    @GetMapping("/notes")
    NoteVO notes(@RequestParam("userId") String userId);

    @PostMapping("/notes")
    NoteVO saveNote(@RequestParam("userId") String userId,
                    @RequestBody UserContentReq.Note req);

    @DeleteMapping("/notes/{id}")
    NoteVO removeNote(@RequestParam("userId") String userId,
                      @PathVariable("id") long id);

    /* -------------------------------- 讨论区 -------------------------------- */

    /** 全部话题（targetType 为空）或某个对象下的话题。 */
    @GetMapping("/discuss")
    DiscussVO discuss(@RequestParam(value = "targetType", required = false) String targetType,
                      @RequestParam(value = "targetId", required = false) String targetId);

    @PostMapping("/discuss")
    DiscussVO createTopic(@RequestParam("userId") String userId,
                          @RequestBody UserContentReq.Topic req);

    @PostMapping("/discuss/{topicId}/floor")
    DiscussVO replyTopic(@RequestParam("userId") String userId,
                         @PathVariable("topicId") String topicId,
                         @RequestBody UserContentReq.Floor req);
}
