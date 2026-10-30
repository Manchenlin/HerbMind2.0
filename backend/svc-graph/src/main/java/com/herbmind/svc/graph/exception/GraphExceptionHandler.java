package com.herbmind.svc.graph.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.bind.MissingServletRequestParameterException;

import com.herbmind.common.R;

/**
 * 补 herbmind-common 的 GlobalExceptionHandler 缺的 4040 分支。
 *
 * 为什么不改 herbmind-common：那是横切资产，改动要三人 review（15 文档 §47-50），
 * 而 4040 目前只有图谱需要。优先级设为最高，保证比 common 的兜底 Exception 处理器先命中。
 */
@RestControllerAdvice
@Order(Ordered.HIGHEST_PRECEDENCE)
public class GraphExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GraphExceptionHandler.class);

    @ExceptionHandler(GraphEntityNotFoundException.class)
    public ResponseEntity<R<Void>> handleNotFound(GraphEntityNotFoundException e) {
        log.info("not found: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(R.fail(4040, e.getMessage() == null ? "实体不存在" : e.getMessage()));
    }

    /**
     * 必填参数缺失 / 类型不对 → 4000 而不是 5000。
     *
     * Spring 抛的是 MissingServletRequestParameterException / MethodArgumentTypeMismatchException，
     * 都不是 IllegalArgumentException，会掉进 common 的兜底分支被算成 5000 ——
     * 契约 §15.4 明确要求「起点/终点缺失」是 4000，所以在本地截住。
     */
    @ExceptionHandler({MissingServletRequestParameterException.class, MethodArgumentTypeMismatchException.class})
    public ResponseEntity<R<Void>> handleBadParam(Exception e) {
        log.warn("bad param: {}", e.getMessage());
        String msg;
        if (e instanceof MissingServletRequestParameterException missing) {
            msg = "缺少必填参数：" + missing.getParameterName();
        } else if (e instanceof MethodArgumentTypeMismatchException mismatch) {
            msg = "参数 " + mismatch.getName() + " 类型不对：" + mismatch.getValue();
        } else {
            msg = "参数错误";
        }
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(R.fail(4000, msg));
    }
}
