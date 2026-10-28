package com.herbmind.contract.identity;

/** 注册请求体。role 不接收前端传入，一律服务端默认 'USER'，防越权提权。 */
public class RegisterReq {

    private String username;
    private String password;
    private String nickname;

    public RegisterReq() {
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getNickname() {
        return nickname;
    }

    public void setNickname(String nickname) {
        this.nickname = nickname;
    }
}
