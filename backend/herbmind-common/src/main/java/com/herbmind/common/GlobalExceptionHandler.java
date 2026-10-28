package com.herbmind.common;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常 → 统一 R&lt;T&gt;（业务 svc 使用；网关不扫描本类）。
 *
 * 09 契约 §0.1 要求「HTTP 状态码同时正确」，所以这里既返回 R 外壳，也设置真实状态码：
 *   IllegalArgumentException → 400 / code 4000
 *   其它                      → 500 / code 5000
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<R<Void>> handleBadRequest(IllegalArgumentException e) {
        log.warn("bad request: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(R.fail(4000, e.getMessage() == null ? "参数错误" : e.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<R<Void>> handleOthers(Exception e) {
        log.error("unexpected error", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(R.fail(5000, e.getMessage() == null ? "服务端错误" : e.getMessage()));
    }
}
