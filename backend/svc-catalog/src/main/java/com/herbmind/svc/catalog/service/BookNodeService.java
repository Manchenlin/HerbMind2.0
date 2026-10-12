package com.herbmind.svc.catalog.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.herbmind.contract.catalog.BookTreeNode;
import com.herbmind.svc.catalog.entity.BookNode;
import com.herbmind.svc.catalog.mapper.BookNodeMapper;

@Service
public class BookNodeService {

    private final BookNodeMapper mapper;

    public BookNodeService(BookNodeMapper mapper) {
        this.mapper = mapper;
    }

    /** 返回某语料的目录树（顶层 parent_id 为空）。无子节点时 children 为空列表。 */
    public List<BookTreeNode> tree(String bookId) {
        List<BookNode> all = mapper.selectList(
                new LambdaQueryWrapper<BookNode>()
                        .eq(BookNode::getBookId, bookId)
                        .orderByAsc(BookNode::getSeq));

        Map<String, List<BookNode>> byParent = all.stream()
                .filter(n -> n.getParentId() != null)
                .collect(Collectors.groupingBy(BookNode::getParentId));

        List<BookTreeNode> roots = new ArrayList<>();
        for (BookNode n : all) {
            if (n.getParentId() == null) {
                roots.add(build(n, byParent));
            }
        }
        return roots;
    }

    public BookTreeNode node(String id) {
        BookNode n = mapper.selectById(id);
        if (n == null) {
            throw new IllegalArgumentException("节点不存在: " + id);
        }
        List<BookNode> children = mapper.selectList(
                new LambdaQueryWrapper<BookNode>().eq(BookNode::getParentId, id));
        List<BookTreeNode> kids = children.stream()
                .map(c -> new BookTreeNode(c.getId(), c.getTitle(), c.getNodeType(), new ArrayList<>()))
                .collect(Collectors.toList());
        return new BookTreeNode(n.getId(), n.getTitle(), n.getNodeType(), kids);
    }

    private BookTreeNode build(BookNode n, Map<String, List<BookNode>> byParent) {
        List<BookTreeNode> kids = byParent.getOrDefault(n.getId(), List.of())
                .stream()
                .map(k -> build(k, byParent))
                .collect(Collectors.toList());
        return new BookTreeNode(n.getId(), n.getTitle(), n.getNodeType(), kids);
    }
}
