package com.herbmind.svc.identity.service;

import java.util.UUID;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.herbmind.contract.identity.LoginReq;
import com.herbmind.contract.identity.LoginResp;
import com.herbmind.contract.identity.RegisterReq;
import com.herbmind.contract.identity.UserDto;
import com.herbmind.svc.identity.entity.AppUser;
import com.herbmind.svc.identity.mapper.AppUserMapper;
import com.herbmind.svc.identity.security.JwtUtil;

/**
 * 用户注册 / 登录 / 查询。
 * 安全约定：密码一律 BCrypt 加密存储，明文不入库、不进日志。
 */
@Service
public class UserService {

    private static final String DEFAULT_ROLE = "USER";

    private final AppUserMapper mapper;
    private final JwtUtil jwt;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();

    public UserService(AppUserMapper mapper, JwtUtil jwt) {
        this.mapper = mapper;
        this.jwt = jwt;
    }

    /** 注册：用户名唯一 → BCrypt 加密 → 签发 token。role 服务端指定，不信任前端传入。 */
    public LoginResp register(RegisterReq req) {
        if (req.getUsername() == null || req.getUsername().isBlank()) {
            throw new IllegalArgumentException("用户名不能为空");
        }
        if (req.getPassword() == null || req.getPassword().length() < 6) {
            throw new IllegalArgumentException("密码至少 6 位");
        }
        Long dup = mapper.selectCount(new LambdaQueryWrapper<AppUser>()
                .eq(AppUser::getUsername, req.getUsername()));
        if (dup != null && dup > 0) {
            throw new IllegalArgumentException("用户名已存在");
        }

        AppUser u = new AppUser();
        u.setId("u_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        u.setUsername(req.getUsername());
        u.setPasswordHash(encoder.encode(req.getPassword()));
        u.setRole(DEFAULT_ROLE);
        u.setNickname(req.getNickname() == null || req.getNickname().isBlank()
                ? req.getUsername() : req.getNickname());
        mapper.insert(u);

        return new LoginResp(jwt.generate(u.getId(), u.getUsername(), u.getRole()), toDto(u));
    }

    /** 登录：校验 BCrypt 密文 → 签发 token。 */
    public LoginResp login(LoginReq req) {
        AppUser u = mapper.selectOne(new LambdaQueryWrapper<AppUser>()
                .eq(AppUser::getUsername, req.getUsername()));
        // 用户不存在与密码错误返回同一提示，避免用户名枚举
        if (u == null || !encoder.matches(req.getPassword(), u.getPasswordHash())) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        return new LoginResp(jwt.generate(u.getId(), u.getUsername(), u.getRole()), toDto(u));
    }

    /** 当前用户（userId 由网关注入的 X-User-Id 得到）。 */
    public UserDto me(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("缺少用户上下文 X-User-Id");
        }
        AppUser u = mapper.selectById(userId);
        if (u == null) {
            throw new IllegalArgumentException("用户不存在: " + userId);
        }
        return toDto(u);
    }

    private UserDto toDto(AppUser u) {
        return new UserDto(u.getId(), u.getUsername(), u.getRole(), u.getNickname(), u.getAvatar());
    }
}
