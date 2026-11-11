package com.herbmind.bff.discuss;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.identity.DiscussVO;
import com.herbmind.contract.identity.IdentityClient;
import com.herbmind.contract.identity.UserContentReq;

/**
 * BFF：讨论区（域2，包 bff/discuss）。
 *
 * 单独一个包而不是塞进 bff/me：讨论是"面向内容"的（挂在方剂/医案/条文下），
 * 和「我的」那几个纯个人数据页不是一类东西；将来内容域要嵌讨论区时，
 * 直接复用这个包的端点，不用从 me 里挑。
 */
@RestController
@RequestMapping("/api/biz/discuss")
public class DiscussController {

    private final IdentityClient identity;

    public DiscussController(IdentityClient identity) {
        this.identity = identity;
    }

    /** 不带参数 = 全部话题；带 targetType/targetId = 某个对象下的讨论。 */
    @GetMapping
    public R<DiscussVO> list(
            @RequestParam(value = "targetType", required = false) String targetType,
            @RequestParam(value = "targetId", required = false) String targetId) {
        return R.ok(identity.discuss(targetType, targetId));
    }

    @PostMapping
    public R<DiscussVO> create(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @RequestBody UserContentReq.Topic req) {
        return R.ok(identity.createTopic(requireUser(userId), req));
    }

    @PostMapping("/{topicId}/floor")
    public R<DiscussVO> reply(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @PathVariable("topicId") String topicId,
            @RequestBody UserContentReq.Floor req) {
        return R.ok(identity.replyTopic(requireUser(userId), topicId, req));
    }

    private String requireUser(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("请先登录再参与讨论");
        }
        return userId;
    }
}
