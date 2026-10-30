package com.herbmind.svc.graph.exception;

/**
 * 实体不存在 → 4040（09 契约 §15 错误码）。
 *
 * 不复用 IllegalArgumentException：那是 4000（参数错误），两者要区分开
 * ——「传错了」与「库里确实没有」前端提示完全不同。
 */
public class GraphEntityNotFoundException extends RuntimeException {

    public GraphEntityNotFoundException(String message) {
        super(message);
    }
}
