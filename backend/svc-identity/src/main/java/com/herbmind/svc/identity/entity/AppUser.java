package com.herbmind.svc.identity.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/**
 * app_user —— 用户表（域2 成长域）。
 * 注意：password_hash 只在本实体内部使用，出参一律转 UserDto（不含该字段）。
 */
@TableName("app_user")
public class AppUser {

    @TableId
    private String id;
    private String username;
    /** BCrypt 密文，绝不明文入库 */
    private String passwordHash;
    private String role;
    private String nickname;
    private String avatar;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public String getNickname() {
        return nickname;
    }

    public void setNickname(String nickname) {
        this.nickname = nickname;
    }

    public String getAvatar() {
        return avatar;
    }

    public void setAvatar(String avatar) {
        this.avatar = avatar;
    }
}
