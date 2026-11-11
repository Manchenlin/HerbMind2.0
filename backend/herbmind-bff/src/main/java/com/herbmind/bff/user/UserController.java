package com.herbmind.bff.user;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.identity.IdentityClient;
import com.herbmind.contract.identity.LoginReq;
import com.herbmind.contract.identity.LoginResp;
import com.herbmind.contract.identity.RegisterReq;
import com.herbmind.contract.identity.UserDto;

/**
 * BFF：用户 / 认证（域2 成长域，包 bff/user）。
 * 前端只调 /api/biz/**；BFF 经 Feign 调 svc-identity 的 /internal/**，统一包 R&lt;T&gt;。
 * 薄层：只做转发与聚合，不写业务规则。
 *
 * 注：/me 依赖网关注入的 X-User-Id，BFF 原样透传。
 */
@RestController
@RequestMapping("/api/biz/user")
public class UserController {

    private final IdentityClient identity;

    public UserController(IdentityClient identity) {
        this.identity = identity;
    }

    @PostMapping("/register")
    public R<LoginResp> register(@RequestBody RegisterReq req) {
        return R.ok(identity.register(req));
    }

    @PostMapping("/login")
    public R<LoginResp> login(@RequestBody LoginReq req) {
        return R.ok(identity.login(req));
    }

    @GetMapping("/me")
    public R<UserDto> me(@RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(identity.me(userId));
    }
}
