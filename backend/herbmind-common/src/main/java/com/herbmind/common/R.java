package com.herbmind.common;

/**
 * 统一响应外壳：{code, msg, data}。
 * 约定：code == 0 表示成功；非 0 即错误（见 09 契约 §0/§12）。
 * JSON 输出为 camelCase（Jackson 默认），不要加 @JsonProperty("..._...")。
 */
public class R<T> {

    private int code;
    private String msg;
    private T data;

    public R() {
    }

    public R(int code, String msg, T data) {
        this.code = code;
        this.msg = msg;
        this.data = data;
    }

    public static <T> R<T> ok(T data) {
        return new R<>(0, "success", data);
    }

    public static <T> R<T> fail(int code, String msg) {
        return new R<>(code, msg, null);
    }

    public int getCode() {
        return code;
    }

    public void setCode(int code) {
        this.code = code;
    }

    public String getMsg() {
        return msg;
    }

    public void setMsg(String msg) {
        this.msg = msg;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }
}
