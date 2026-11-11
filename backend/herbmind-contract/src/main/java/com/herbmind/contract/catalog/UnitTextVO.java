package com.herbmind.contract.catalog;

/**
 * 一条知识单元的正文（原书文字原样返回，不做任何改写）。
 *
 * <p>为什么要单独开这个 VO：节点详情 `NodeDetailVO` 只带方剂/医案的摘要（名称、证候、页码），
 * 正文都在 `content_unit.content` 里（实测原书 95.5% 的文字都在这一列），
 * 前端要"按原书顺序读一节"就必须拿到这些正文。
 *
 * @param id       单元 id
 * @param refType  formula / case / node
 * @param refId    关联对象 id
 * @param title    单元标题（方名 / 医案名 / 节名）
 * @param unitType full / theory
 * @param page     原书页码（形如「第19-22页」，可能为空串）
 * @param content  正文原文
 */
public record UnitTextVO(
        String id,
        String refType,
        String refId,
        String title,
        String unitType,
        String page,
        String content) {
}
