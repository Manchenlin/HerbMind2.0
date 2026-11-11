package com.herbmind.contract.identity;

/**
 * 用户公开信息（不含 password_hash —— 绝不外泄）。
 * 字段 camelCase，供 BFF 直接包 R&lt;T&gt; 返前端。
 */
public class UserDto {

    private String id;
    private String username;
    private String role;
    private String nickname;
    private String avatar;

    public UserDto() {
    }

    public UserDto(String id, String username, String role, String nickname, String avatar) {
        this.id = id;
        this.username = username;
        this.role = role;
        this.nickname = nickname;
        this.avatar = avatar;
    }

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
