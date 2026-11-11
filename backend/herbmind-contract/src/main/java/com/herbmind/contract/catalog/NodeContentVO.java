package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 目录节点下的全部正文，按原书顺序排列（前端"典籍阅读"用它还原原书版面）。
 *
 * @param nodeId    节点 id
 * @param nodeTitle 节点标题
 * @param bookId    所属语料 id
 * @param bookTitle 所属语料标题
 * @param units     该节点子树下所有知识单元，按原书页码升序
 */
public record NodeContentVO(
        String nodeId,
        String nodeTitle,
        String bookId,
        String bookTitle,
        List<UnitTextVO> units) {
}
