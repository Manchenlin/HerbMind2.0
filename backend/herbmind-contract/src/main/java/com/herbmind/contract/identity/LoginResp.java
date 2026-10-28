package com.herbmind.contract.identity;

/**
 * 登录 / 注册响应（裸 DTO，供 BFF 包 R&lt;LoginResp&gt;）。
 * 前端拿 token 放 Authorization: Bearer &lt;token&gt;。
 */
public class LoginResp {

    private String token;
    private UserDto user;

    public LoginResp() {
    }

    public LoginResp(String token, UserDto user) {
        this.token = token;
        this.user = user;
    }

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }

    public UserDto getUser() {
        return user;
    }

    public void setUser(UserDto user) {
        this.user = user;
    }
}
