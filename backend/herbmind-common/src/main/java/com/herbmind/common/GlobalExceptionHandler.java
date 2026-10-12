package com.herbmind.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常 → 统一 R&lt;T&gt;（业务 svc 使用；网关不扫描本类）。
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(IllegalArgumentException.class)
    public R<Void> handleBadRequest(IllegalArgumentException e) {
        log.warn("bad request: {}", e.getMessage());
        return R.fail(4000, e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public R<Void> handleOthers(Exception e) {
        log.error("unexpected error", e);
        return R.fail(5000, e.getMessage() == null ? "服务端错误" : e.getMessage());
    }
}
