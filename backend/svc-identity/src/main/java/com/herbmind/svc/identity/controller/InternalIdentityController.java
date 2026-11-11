package com.herbmind.svc.identity.controller;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.contract.identity.DiscussVO;
import com.herbmind.contract.identity.FavoriteVO;
import com.herbmind.contract.identity.LoginReq;
import com.herbmind.contract.identity.LoginResp;
import com.herbmind.contract.identity.NoteVO;
import com.herbmind.contract.identity.RegisterReq;
import com.herbmind.contract.identity.UserContentReq;
import com.herbmind.contract.identity.UserDto;
import com.herbmind.svc.identity.service.UserContentService;
import com.herbmind.svc.identity.service.UserService;

/**
 * 内部接口（/internal/**，不进网关）。
 * 返回**裸 DTO**（不包 R），由 BFF 统一包 R&lt;T&gt; 给前端。
 * 错误：抛 IllegalArgumentException → GlobalExceptionHandler 转 R.fail(4000, msg)。
 *
 * 收藏 / 笔记 / 讨论与用户同域，放在这个服务里；userId 由 BFF 从 X-User-Id 透传进来。
 */
@RestController
@RequestMapping("/internal/identity")
public class InternalIdentityController {

    private final UserService service;
    private final UserContentService content;

    public InternalIdentityController(UserService service, UserContentService content) {
        this.service = service;
        this.content = content;
    }

    @PostMapping("/user/register")
    public LoginResp register(@RequestBody RegisterReq req) {
        return service.register(req);
    }

    @PostMapping("/user/login")
    public LoginResp login(@RequestBody LoginReq req) {
        return service.login(req);
    }

    @GetMapping("/user/me")
    public UserDto me(@RequestHeader(value = "X-User-Id", required = false) String userId) {
        return service.me(userId);
    }

    // ------------------------------------------------------------------ 收藏

    @GetMapping("/favorites")
    public FavoriteVO favorites(@RequestParam("userId") String userId) {
        requireUser(userId);
        return content.favorites(userId);
    }

    @PostMapping("/favorites")
    public FavoriteVO addFavorite(@RequestParam("userId") String userId,
                                  @RequestBody UserContentReq.Favorite req) {
        requireUser(userId);
        return content.addFavorite(userId, req);
    }

    @DeleteMapping("/favorites/{id}")
    public FavoriteVO removeFavorite(@RequestParam("userId") String userId,
                                     @PathVariable("id") long id) {
        requireUser(userId);
        return content.removeFavorite(userId, id);
    }

    // ------------------------------------------------------------------ 笔记

    @GetMapping("/notes")
    public NoteVO notes(@RequestParam("userId") String userId) {
        requireUser(userId);
        return content.notes(userId);
    }

    @PostMapping("/notes")
    public NoteVO saveNote(@RequestParam("userId") String userId,
                           @RequestBody UserContentReq.Note req) {
        requireUser(userId);
        return content.saveNote(userId, req);
    }

    @DeleteMapping("/notes/{id}")
    public NoteVO removeNote(@RequestParam("userId") String userId,
                             @PathVariable("id") long id) {
        requireUser(userId);
        return content.removeNote(userId, id);
    }

    // ------------------------------------------------------------------ 讨论

    @GetMapping("/discuss")
    public DiscussVO discuss(@RequestParam(value = "targetType", required = false) String targetType,
                             @RequestParam(value = "targetId", required = false) String targetId) {
        return content.discuss(targetType, targetId);
    }

    @PostMapping("/discuss")
    public DiscussVO createTopic(@RequestParam("userId") String userId,
                                 @RequestBody UserContentReq.Topic req) {
        requireUser(userId);
        return content.createTopic(userId, req);
    }

    @PostMapping("/discuss/{topicId}/floor")
    public DiscussVO reply(@RequestParam("userId") String userId,
                           @PathVariable("topicId") String topicId,
                           @RequestBody UserContentReq.Floor req) {
        requireUser(userId);
        return content.reply(userId, topicId, req);
    }

    private void requireUser(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("缺少用户上下文（userId）");
        }
    }
}
