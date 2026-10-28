package com.herbmind.svc.catalog.service;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.herbmind.contract.catalog.BookTreeNode;
import com.herbmind.contract.catalog.BookVO;
import com.herbmind.contract.catalog.CaseBriefVO;
import com.herbmind.contract.catalog.CaseSectionVO;
import com.herbmind.contract.catalog.CaseVO;
import com.herbmind.contract.catalog.FormulaBriefVO;
import com.herbmind.contract.catalog.FormulaVO;
import com.herbmind.contract.catalog.GraphPreviewVO;
import com.herbmind.contract.catalog.HerbVO;
import com.herbmind.contract.catalog.ImportRequest;
import com.herbmind.contract.catalog.ImportStatusVO;
import com.herbmind.contract.catalog.LinkVO;
import com.herbmind.contract.catalog.NodeDetailVO;
import com.herbmind.contract.catalog.QuoteItemVO;
import com.herbmind.contract.catalog.QuoteListVO;
import com.herbmind.contract.catalog.QuoteRefVO;
import com.herbmind.contract.catalog.QuoteVO;
import com.herbmind.svc.catalog.entity.Book;
import com.herbmind.svc.catalog.entity.BookNode;
import com.herbmind.svc.catalog.entity.CaseRecord;
import com.herbmind.svc.catalog.entity.CaseSection;
import com.herbmind.svc.catalog.entity.Classic;
import com.herbmind.svc.catalog.entity.ClassicQuote;
import com.herbmind.svc.catalog.entity.Formula;
import com.herbmind.svc.catalog.entity.FormulaHerb;
import com.herbmind.svc.catalog.mapper.BookMapper;
import com.herbmind.svc.catalog.mapper.BookNodeMapper;
import com.herbmind.svc.catalog.mapper.CaseRecordMapper;
import com.herbmind.svc.catalog.mapper.CaseSectionMapper;
import com.herbmind.svc.catalog.mapper.ClassicMapper;
import com.herbmind.svc.catalog.mapper.ClassicQuoteMapper;
import com.herbmind.svc.catalog.mapper.FormulaHerbMapper;
import com.herbmind.svc.catalog.mapper.FormulaMapper;

/**
 * 内容域（读）核心服务：书架 / 目录 / 方剂 / 医案 / 条文 / 导入 / 首页预览。
 *
 * 设计取舍：全库只有 245 方 / 290 案 / 568 条文，联表在 Java 内组装（多次小查询 + 内存 join）
 * 比写一堆 XML 更直观、更易改；超大数据量时再下沉为 SQL join。
 */
@Service
public class CatalogService {

    private static final int MAX_LINKS = 5;
    private static final int MAX_QUOTE_REFS = 6;
    private static final DateTimeFormatter ISO = DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    private final BookMapper bookMapper;
    private final BookNodeMapper nodeMapper;
    private final ClassicMapper classicMapper;
    private final FormulaMapper formulaMapper;
    private final FormulaHerbMapper herbMapper;
    private final CaseRecordMapper caseMapper;
    private final CaseSectionMapper sectionMapper;
    private final ClassicQuoteMapper quoteMapper;
    private final BookNodeService bookNodeService;
    private final QuoteParser quoteParser;

    public CatalogService(BookMapper bookMapper,
                          BookNodeMapper nodeMapper,
                          ClassicMapper classicMapper,
                          FormulaMapper formulaMapper,
                          FormulaHerbMapper herbMapper,
                          CaseRecordMapper caseMapper,
                          CaseSectionMapper sectionMapper,
                          ClassicQuoteMapper quoteMapper,
                          BookNodeService bookNodeService,
                          QuoteParser quoteParser) {
        this.bookMapper = bookMapper;
        this.nodeMapper = nodeMapper;
        this.classicMapper = classicMapper;
        this.formulaMapper = formulaMapper;
        this.herbMapper = herbMapper;
        this.caseMapper = caseMapper;
        this.sectionMapper = sectionMapper;
        this.quoteMapper = quoteMapper;
        this.bookNodeService = bookNodeService;
        this.quoteParser = quoteParser;
    }

    // ==================== 书架 / 目录 ====================

    public List<BookVO> books() {
        List<Book> books = bookMapper.selectList(new QueryWrapper<Book>().orderByAsc("id"));
        List<BookVO> out = new ArrayList<>();
        for (Book b : books) {
            out.add(toBookVO(b,
                    bookMapper.countUnits(b.getId()),
                    bookMapper.countNodes(b.getId()),
                    bookMapper.countFormulas(b.getId()),
                    bookMapper.countCases(b.getId())));
        }
        return out;
    }

    public List<BookTreeNode> tree(String bookId) {
        return bookNodeService.tree(bookId);
    }

    public NodeDetailVO nodeDetail(String id) {
        BookNode node = nodeMapper.selectById(id);
        if (node == null) {
            throw new IllegalArgumentException("节点不存在: " + id);
        }
        Book book = bookMapper.selectById(node.getBookId());
        List<BookNode> all = nodesOfBook(node.getBookId());
        Set<String> subtree = subtreeIds(node.getId(), all);

        List<Formula> formulas = formulasByNodeIds(subtree);
        Map<String, List<HerbVO>> herbMap = herbsOf(formulas.stream().map(Formula::getId).toList());
        List<FormulaBriefVO> formulaBriefs = formulas.stream()
                .map(f -> toFormulaBrief(f, herbMap))
                .toList();

        List<CaseBriefVO> cases = new ArrayList<>();
        List<String> formulaIds = formulas.stream().map(Formula::getId).toList();
        if (!formulaIds.isEmpty()) {
            List<CaseRecord> records = caseMapper.selectList(
                    new QueryWrapper<CaseRecord>().in("main_formula_id", formulaIds));
            Map<String, String> formulaNames = formulas.stream()
                    .collect(Collectors.toMap(Formula::getId, Formula::getName, (a, b) -> a));
            for (CaseRecord c : records) {
                cases.add(toCaseBrief(c, formulaNames.get(c.getMainFormulaId())));
            }
        }

        List<Formula> bookFormulas = formulasOfBook(node.getBookId());
        List<QuoteRefVO> quotes = quoteRefs(node.getBookId(), namesOf(bookFormulas), MAX_QUOTE_REFS);

        List<BookTreeNode> kids = all.stream()
                .filter(n -> Objects.equals(n.getParentId(), node.getId()))
                .sorted(Comparator.comparing(n -> n.getSeq() == null ? 0 : n.getSeq()))
                .map(n -> new BookTreeNode(n.getId(), n.getTitle(), n.getNodeType(), new ArrayList<>()))
                .toList();

        return new NodeDetailVO(
                new BookTreeNode(node.getId(), node.getTitle(), node.getNodeType(), kids),
                node.getBookId(),
                book == null ? null : book.getTitle(),
                node.getClassicId(),
                node.getParentId(),
                node.getPathText(),
                breadcrumb(node, all),
                formulaBriefs,
                cases,
                quotes,
                kids.size());
    }

    // ==================== 方剂 / 医案 / 条文 ====================

    public FormulaVO formula(String id) {
        Formula f = formulaMapper.selectById(id);
        if (f == null) {
            throw new IllegalArgumentException("方剂不存在: " + id);
        }
        BookNode node = f.getNodeId() == null ? null : nodeMapper.selectById(f.getNodeId());
        Book book = node == null ? null : bookMapper.selectById(node.getBookId());
        Classic classic = node == null || node.getClassicId() == null ? null
                : classicMapper.selectById(node.getClassicId());

        List<HerbVO> herbs = herbsOf(List.of(f.getId())).getOrDefault(f.getId(), List.of());

        List<CaseRecord> records = caseMapper.selectList(
                new QueryWrapper<CaseRecord>().eq("main_formula_id", f.getId()));
        List<CaseBriefVO> cases = records.stream().map(c -> toCaseBrief(c, f.getName())).toList();

        List<QuoteRefVO> quotes = quoteRefs(book == null ? null : book.getId(),
                namesOf(List.of(f)), MAX_QUOTE_REFS);
        List<Formula> relatedPool = book == null ? formulaMapper.selectList(null) : formulasOfBook(book.getId());

        return new FormulaVO(
                f.getId(), f.getName(), f.getPinyin(), f.getAlias(),
                f.getEfficacy(), f.getSyndromeText(), f.getSourceText(), f.getPage(),
                f.getNodeId(), node == null ? null : node.getTitle(),
                book == null ? null : book.getId(), book == null ? null : book.getTitle(),
                classic == null ? null : classic.getName(),
                chapterOf(node, nodesOfBook(node == null ? null : node.getBookId())),
                herbs, quotes, cases,
                relatedFormulas(f, relatedPool, herbs));
    }

    public CaseVO caseDetail(String id) {
        CaseRecord c = caseMapper.selectById(id);
        if (c == null) {
            throw new IllegalArgumentException("医案不存在: " + id);
        }
        List<CaseSection> sections = sectionMapper.selectList(
                new QueryWrapper<CaseSection>().eq("case_id", id).orderByAsc("seq"));

        Formula main = c.getMainFormulaId() == null ? null : formulaMapper.selectById(c.getMainFormulaId());
        BookNode node = main == null || main.getNodeId() == null ? null : nodeMapper.selectById(main.getNodeId());
        Book book = node == null ? null : bookMapper.selectById(node.getBookId());
        String chapter = chapterOf(node, nodesOfBook(node == null ? null : node.getBookId()));

        List<QuoteRefVO> quotes = main == null ? List.of()
                : quoteRefs(book == null ? null : book.getId(), namesOf(List.of(main)), MAX_QUOTE_REFS);

        // 同一主方下的其它医案：前端「案例一 / 二 / 三」切换（02 §M2、prototype/case.html）
        List<CaseBriefVO> siblings = new ArrayList<>();
        if (main != null) {
            for (CaseRecord s : caseMapper.selectList(new QueryWrapper<CaseRecord>()
                    .eq("main_formula_id", main.getId())
                    .ne("id", id)
                    .orderByAsc("id")
                    .last("limit 8"))) {
                siblings.add(toCaseBrief(s, main.getName()));
            }
        }

        return new CaseVO(
                c.getId(), c.getTitle(), c.getUnitType(),
                c.getMainFormulaId(), main == null ? null : main.getName(),
                c.getSyndromeText(), c.getPage(),
                book == null ? null : book.getId(), book == null ? null : book.getTitle(), chapter,
                sections.stream()
                        .map(s -> new CaseSectionVO(s.getId(), s.getKind(), s.getContent(),
                                s.getSeq() == null ? 0 : s.getSeq()))
                        .toList(),
                quotes,
                siblings);
    }

    /**
     * 条文列表（A1 的 `/quote/list`）：支持按语料 / 经典 / 关键词过滤 + 分页。
     * 列表项给 240 字摘录，完整原文走 `/quote/{id}`。
     */
    public QuoteListVO quoteList(String q, String bookId, String classicId, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), 100);

        QueryWrapper<ClassicQuote> w = new QueryWrapper<>();
        String kw = q == null ? "" : q.trim();
        if (classicId != null && !classicId.isBlank()) {
            w.eq("classic_id", classicId.trim());
        } else if (bookId != null && !bookId.isBlank()) {
            List<String> ids = classicMapper.selectList(
                            new QueryWrapper<Classic>().eq("book_id", bookId.trim()))
                    .stream().map(Classic::getId).toList();
            if (ids.isEmpty()) {
                return new QuoteListVO(List.of(), 0, p, s);
            }
            w.in("classic_id", ids);
        }
        if (!kw.isEmpty()) {
            w.like("content", kw);
        }

        long total = quoteMapper.selectCount(w);
        w.orderByAsc("classic_id", "id").last("limit " + s + " offset " + (p - 1) * s);
        List<ClassicQuote> rows = quoteMapper.selectList(w);

        Map<String, String> classicNames = classicNames();
        List<QuoteRefVO> list = new ArrayList<>();
        for (ClassicQuote row : rows) {
            String cn = classicNames.get(row.getClassicId());
            String text = row.getContent() == null ? "" : row.getContent().replaceAll("\\s+", " ").trim();
            String excerpt = text.length() <= 240 ? text : text.substring(0, 240) + "…";
            list.add(new QuoteRefVO(row.getId(), row.getArticleNo(), cn, excerpt,
                    row.getPlainText(), row.getPage(), label(cn, row.getArticleNo())));
        }
        return new QuoteListVO(list, total, p, s);
    }

    public QuoteVO quote(String id) {
        ClassicQuote q = quoteMapper.selectById(id);
        if (q == null) {
            throw new IllegalArgumentException("条文不存在: " + id);
        }
        Classic classic = q.getClassicId() == null ? null : classicMapper.selectById(q.getClassicId());
        Book book = classic == null ? null : bookMapper.selectById(classic.getBookId());
        String classicName = classic == null ? null : classic.getName();

        List<Formula> candidates = formulasOfBook(book == null ? null : book.getId());
        if (candidates.isEmpty()) {
            candidates = formulaMapper.selectList(null);
        }
        Map<String, String> formulaNames = new HashMap<>();
        List<LinkVO> formulaLinks = new ArrayList<>();
        List<LinkVO> caseLinks = new ArrayList<>();
        Set<String> caseSeen = new LinkedHashSet<>();

        List<QuoteItemVO> items = new ArrayList<>();
        for (QuoteItemVO item : quoteParser.parse(q.getContent())) {
            List<LinkVO> fl = matchFormulas(item.text(), candidates, MAX_LINKS);
            for (LinkVO l : fl) {
                if (formulaNames.putIfAbsent(l.id(), l.name()) == null) {
                    formulaLinks.add(l);
                }
            }
            List<LinkVO> cl = matchCases(item.text(), fl);
            for (LinkVO l : cl) {
                if (caseSeen.add(l.id())) {
                    caseLinks.add(l);
                }
            }
            items.add(new QuoteItemVO(item.no(), item.text(),
                    label(classicName, item.no()), fl, cl));
        }

        return new QuoteVO(
                q.getId(), q.getArticleNo(), q.getClassicId(), classicName,
                book == null ? null : book.getId(), book == null ? null : book.getTitle(),
                q.getContent(), q.getPlainText(), q.getPage(),
                label(classicName, q.getArticleNo()),
                items, formulaLinks, caseLinks);
    }

    public FormulaVO daily(String bookId) {
        List<Formula> formulas = formulasOfBook(bookId);
        if (formulas.isEmpty()) {
            formulas = formulaMapper.selectList(null);
        }
        if (formulas.isEmpty()) {
            throw new IllegalArgumentException("内容库为空，请先执行 init-data.sh 导入数据");
        }
        int idx = (int) Math.floorMod(LocalDate.now().toEpochDay(), formulas.size());
        return formula(formulas.get(idx).getId());
    }

    public List<FormulaBriefVO> batch(List<String> ids, List<String> names) {
        List<Formula> found = new ArrayList<>();
        if (ids != null && !ids.isEmpty()) {
            found.addAll(formulaMapper.selectList(new QueryWrapper<Formula>().in("id", ids)));
        }
        if (names != null && !names.isEmpty()) {
            found.addAll(formulaMapper.selectList(new QueryWrapper<Formula>().in("name", names)));
        }
        Map<String, Formula> uniq = new LinkedHashMap<>();
        for (Formula f : found) {
            uniq.putIfAbsent(f.getId(), f);
        }
        Map<String, List<HerbVO>> herbMap = herbsOf(uniq.keySet().stream().toList());
        return uniq.values().stream().map(f -> toFormulaBrief(f, herbMap)).toList();
    }

    // ==================== 首页图谱预览 ====================

    public GraphPreviewVO graphPreview(String formulaId) {
        Formula f = formulaMapper.selectById(formulaId);
        if (f == null) {
            throw new IllegalArgumentException("方剂不存在: " + formulaId);
        }
        List<GraphPreviewVO.GraphNodeVO> nodes = new ArrayList<>();
        List<GraphPreviewVO.GraphEdgeVO> edges = new ArrayList<>();
        String center = "f:" + f.getId();
        nodes.add(new GraphPreviewVO.GraphNodeVO(center, "Formula", f.getName(), 0));

        List<HerbVO> herbs = herbsOf(List.of(f.getId())).getOrDefault(f.getId(), List.of());
        int i = 1;
        for (HerbVO h : herbs) {
            String hid = "h:" + h.name();
            nodes.add(new GraphPreviewVO.GraphNodeVO(hid, "Herb", h.name(), 1 + (i++ % 2)));
            edges.add(new GraphPreviewVO.GraphEdgeVO(center, hid, "COMPOSED_OF"));
        }
        if (f.getSyndromeText() != null && !f.getSyndromeText().isBlank()) {
            String sid = "s:" + f.getId();
            nodes.add(new GraphPreviewVO.GraphNodeVO(sid, "Syndrome", shorten(f.getSyndromeText(), 12), 1));
            edges.add(new GraphPreviewVO.GraphEdgeVO(center, sid, "INDICATES"));
        }
        List<CaseRecord> cases = caseMapper.selectList(
                new QueryWrapper<CaseRecord>().eq("main_formula_id", f.getId()).last("limit 2"));
        for (CaseRecord c : cases) {
            String cid = "c:" + c.getId();
            nodes.add(new GraphPreviewVO.GraphNodeVO(cid, "Case", shorten(c.getTitle(), 10), 2));
            edges.add(new GraphPreviewVO.GraphEdgeVO(center, cid, "HAS_CASE"));
        }
        return new GraphPreviewVO(nodes, edges, f.getId());
    }

    // ==================== 导入（UGC） ====================

    public ImportStatusVO importBook(ImportRequest req) {
        if (req == null || req.title() == null || req.title().isBlank()) {
            throw new IllegalArgumentException("书名不能为空");
        }
        String bookType = req.bookType() == null || req.bookType().isBlank() ? "fz" : req.bookType();
        if (!List.of("fz", "bencao", "drug", "case").contains(bookType)) {
            throw new IllegalArgumentException("bookType 只允许 fz / bencao / drug / case");
        }
        String id = "bk_u" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);

        Book b = new Book();
        b.setId(id);
        b.setTitle(req.title().trim());
        b.setBookType(bookType);
        b.setAuthor(req.author());
        b.setDynasty(req.dynasty());
        b.setSourceLicense(req.sourceLicense());
        b.setIngestStatus("draft");
        b.setCreatedAt(OffsetDateTime.now());
        bookMapper.insert(b);

        return new ImportStatusVO(id, id, b.getTitle(), "待复核",
                "已登记语料；等待治理审核（域3）通过后进入书架并可检索。"
                        + " 解析 / 向量化由 ETL 在审核通过后执行。",
                ISO.format(b.getCreatedAt()));
    }

    public ImportStatusVO importStatus(String importId) {
        Book b = bookMapper.selectById(importId);
        if (b == null) {
            throw new IllegalArgumentException("导入记录不存在: " + importId);
        }
        String status = switch (b.getIngestStatus() == null ? "" : b.getIngestStatus()) {
            case "draft" -> "待复核";
            case "已发布" -> "已发布";
            default -> b.getIngestStatus();
        };
        return new ImportStatusVO(b.getId(), b.getId(), b.getTitle(), status,
                "解析与向量化状态由 ETL 回写；当前仅登记了语料元信息。",
                b.getCreatedAt() == null ? null : ISO.format(b.getCreatedAt()));
    }

    // ==================== 内部工具 ====================

    private BookVO toBookVO(Book b, long units, long nodes, long formulas, long cases) {
        return new BookVO(
                b.getId(), b.getTitle(), b.getBookType(), bookTypeLabel(b.getBookType()),
                b.getAuthor(), b.getDynasty(), b.getEdition(), b.getSourceLicense(),
                b.getIngestStatus(), statusLabel(b.getIngestStatus()),
                b.getCreatedAt() == null ? null : ISO.format(b.getCreatedAt()),
                units, nodes, formulas, cases);
    }

    private static String bookTypeLabel(String t) {
        if (t == null) {
            return "未分类";
        }
        return switch (t) {
            case "fz" -> "方证 · 医案";
            case "bencao" -> "本草";
            case "drug" -> "药品";
            case "case" -> "医案";
            default -> t;
        };
    }

    private static String statusLabel(String s) {
        if (s == null) {
            return "未知";
        }
        return switch (s) {
            case "draft" -> "待审核";
            case "已发布" -> "已发布";
            case "整理中" -> "整理中";
            default -> s;
        };
    }

    private List<BookNode> nodesOfBook(String bookId) {
        if (bookId == null) {
            return List.of();
        }
        return nodeMapper.selectList(new QueryWrapper<BookNode>()
                .eq("book_id", bookId)
                .orderByAsc("seq"));
    }

    private Set<String> subtreeIds(String rootId, List<BookNode> all) {
        Map<String, List<String>> children = new HashMap<>();
        for (BookNode n : all) {
            if (n.getParentId() != null) {
                children.computeIfAbsent(n.getParentId(), k -> new ArrayList<>()).add(n.getId());
            }
        }
        Set<String> ids = new LinkedHashSet<>();
        Deque<String> queue = new ArrayDeque<>();
        queue.add(rootId);
        while (!queue.isEmpty()) {
            String cur = queue.poll();
            if (!ids.add(cur)) {
                continue;
            }
            queue.addAll(children.getOrDefault(cur, List.of()));
        }
        return ids;
    }

    private List<Formula> formulasByNodeIds(Collection<String> nodeIds) {
        if (nodeIds == null || nodeIds.isEmpty()) {
            return List.of();
        }
        return formulaMapper.selectList(new QueryWrapper<Formula>().in("node_id", nodeIds));
    }

    /** bookId 为 null 时返回全库方剂。 */
    private List<Formula> formulasOfBook(String bookId) {
        if (bookId == null) {
            return formulaMapper.selectList(null);
        }
        Set<String> nodeIds = nodesOfBook(bookId).stream()
                .map(BookNode::getId)
                .collect(Collectors.toCollection(LinkedHashSet::new));
        if (nodeIds.isEmpty()) {
            return List.of();
        }
        return formulasByNodeIds(nodeIds);
    }

    private Map<String, List<HerbVO>> herbsOf(List<String> formulaIds) {
        if (formulaIds == null || formulaIds.isEmpty()) {
            return Map.of();
        }
        List<FormulaHerb> rows = herbMapper.selectList(new QueryWrapper<FormulaHerb>()
                .in("formula_id", formulaIds)
                .orderByAsc("seq"));
        Map<String, List<HerbVO>> out = new LinkedHashMap<>();
        for (FormulaHerb h : rows) {
            out.computeIfAbsent(h.getFormulaId(), k -> new ArrayList<>())
                    .add(new HerbVO(h.getHerbName(), h.getDose(), h.getUnit(), h.getRole(),
                            h.getSeq() == null ? 0 : h.getSeq()));
        }
        return out;
    }

    private FormulaBriefVO toFormulaBrief(Formula f, Map<String, List<HerbVO>> herbMap) {
        return new FormulaBriefVO(f.getId(), f.getName(), f.getEfficacy(), f.getSyndromeText(),
                f.getPage(), f.getNodeId(), null,
                herbMap.getOrDefault(f.getId(), List.of()));
    }

    private CaseBriefVO toCaseBrief(CaseRecord c, String formulaName) {
        return new CaseBriefVO(c.getId(), c.getTitle(), c.getMainFormulaId(), formulaName,
                c.getSyndromeText(), c.getPage());
    }

    private List<LinkVO> breadcrumb(BookNode node, List<BookNode> all) {
        Map<String, BookNode> byId = all.stream()
                .collect(Collectors.toMap(BookNode::getId, n -> n, (a, b) -> a));
        List<LinkVO> chain = new ArrayList<>();
        BookNode cur = node.getParentId() == null ? null : byId.get(node.getParentId());
        int guard = 0;
        while (cur != null && guard++ < 20) {
            chain.add(0, new LinkVO(cur.getId(), cur.getTitle()));
            cur = cur.getParentId() == null ? null : byId.get(cur.getParentId());
        }
        return chain;
    }

    private String chapterOf(BookNode node, List<BookNode> all) {
        if (node == null) {
            return null;
        }
        Map<String, BookNode> byId = all.stream()
                .collect(Collectors.toMap(BookNode::getId, n -> n, (a, b) -> a));
        BookNode cur = node;
        int guard = 0;
        while (cur != null && guard++ < 20) {
            if ("section".equals(cur.getNodeType()) || "chapter".equals(cur.getNodeType())) {
                return cur.getTitle();
            }
            cur = cur.getParentId() == null ? null : byId.get(cur.getParentId());
        }
        return node.getTitle();
    }

    private List<FormulaBriefVO> relatedFormulas(Formula self, List<Formula> pool,
                                                 List<HerbVO> selfHerbs) {
        Map<String, FormulaBriefVO> out = new LinkedHashMap<>();
        if (self.getNodeId() != null) {
            for (Formula f : pool) {
                if (!f.getId().equals(self.getId()) && self.getNodeId().equals(f.getNodeId())) {
                    out.putIfAbsent(f.getId(), new FormulaBriefVO(f.getId(), f.getName(),
                            f.getEfficacy(), f.getSyndromeText(), f.getPage(), f.getNodeId(), null,
                            List.of()));
                }
                if (out.size() >= 6) {
                    break;
                }
            }
        }
        if (out.isEmpty()) {
            Set<String> mine = selfHerbs.stream().map(HerbVO::name).collect(Collectors.toSet());
            List<Formula> all = pool.isEmpty() ? formulaMapper.selectList(null) : pool;
            Map<String, List<String>> herbNames = new HashMap<>();
            List<String> allIds = all.stream().map(Formula::getId).toList();
            if (mine.isEmpty() || allIds.isEmpty()) {
                return new ArrayList<>(out.values());
            }
            for (FormulaHerb h : herbMapper.selectList(new QueryWrapper<FormulaHerb>()
                    .in("formula_id", allIds))) {
                herbNames.computeIfAbsent(h.getFormulaId(), k -> new ArrayList<>()).add(h.getHerbName());
            }
            for (Formula f : all) {
                if (f.getId().equals(self.getId())) {
                    continue;
                }
                List<String> hs = herbNames.getOrDefault(f.getId(), List.of());
                if (hs.stream().anyMatch(mine::contains)) {
                    out.putIfAbsent(f.getId(), new FormulaBriefVO(f.getId(), f.getName(),
                            f.getEfficacy(), f.getSyndromeText(), f.getPage(), f.getNodeId(), null,
                            List.of()));
                }
                if (out.size() >= 6) {
                    break;
                }
            }
        }
        return new ArrayList<>(out.values());
    }

    private List<String> namesOf(List<Formula> formulas) {
        List<String> names = new ArrayList<>();
        for (Formula f : formulas) {
            addName(names, f.getName());
            addName(names, f.getAlias());
            String n = f.getName();
            if (n != null) {
                int a = n.indexOf('（');
                int b = n.indexOf('）');
                if (a > 0 && b > a) {
                    addName(names, n.substring(a + 1, b));
                }
            }
        }
        return names;
    }

    private void addName(List<String> names, String raw) {
        if (raw == null || raw.isBlank()) {
            return;
        }
        for (String part : raw.split("[、,，/；;]")) {
            String p = part.trim();
            if (p.length() >= 2 && !names.contains(p)) {
                names.add(p);
            }
        }
    }

    private List<LinkVO> matchFormulas(String text, List<Formula> candidates, int limit) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        List<LinkVO> out = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (Formula f : candidates) {
            if (out.size() >= limit) {
                break;
            }
            for (String name : namesOf(List.of(f))) {
                if (text.contains(name) && seen.add(f.getId())) {
                    out.add(new LinkVO(f.getId(), f.getName()));
                    break;
                }
            }
        }
        return out;
    }

    private List<LinkVO> matchCases(String text, List<LinkVO> formulaLinks) {
        if (formulaLinks.isEmpty()) {
            return List.of();
        }
        List<String> ids = formulaLinks.stream().map(LinkVO::id).toList();
        List<CaseRecord> records = caseMapper.selectList(
                new QueryWrapper<CaseRecord>().in("main_formula_id", ids).last("limit 3"));
        List<LinkVO> out = new ArrayList<>();
        for (CaseRecord c : records) {
            out.add(new LinkVO(c.getId(), c.getTitle()));
        }
        return out;
    }

    /** 在某个语料的条文里找引用（含某方名的条文）。 */
    private List<QuoteRefVO> quoteRefs(String bookId, List<String> names, int limit) {
        if (names.isEmpty()) {
            return List.of();
        }
        List<ClassicQuote> quotes = quotesOfBook(bookId);
        Map<String, String> classicNames = classicNames();
        List<QuoteRefVO> out = new ArrayList<>();
        for (ClassicQuote q : quotes) {
            for (QuoteItemVO item : quoteParser.parse(q.getContent())) {
                boolean hit = names.stream().anyMatch(n -> item.text().contains(n));
                if (!hit) {
                    continue;
                }
                String cn = classicNames.get(q.getClassicId());
                out.add(new QuoteRefVO(q.getId(), item.no(), cn, item.text(),
                        q.getPlainText(), q.getPage(), label(cn, item.no())));
                if (out.size() >= limit) {
                    return out;
                }
            }
        }
        return out;
    }

    private List<ClassicQuote> quotesOfBook(String bookId) {
        if (bookId == null) {
            return quoteMapper.selectList(null);
        }
        List<String> classicIds = classicMapper.selectList(
                        new QueryWrapper<Classic>().eq("book_id", bookId))
                .stream().map(Classic::getId).toList();
        if (classicIds.isEmpty()) {
            return List.of();
        }
        return quoteMapper.selectList(new QueryWrapper<ClassicQuote>().in("classic_id", classicIds));
    }

    private Map<String, String> classicNames() {
        Map<String, String> out = new HashMap<>();
        for (Classic c : classicMapper.selectList(null)) {
            out.put(c.getId(), c.getName());
        }
        return out;
    }

    private static String label(String classicName, String no) {
        String base = classicName == null ? "条文" : "《" + classicName + "》";
        return no == null ? base : base + "第 " + no + " 条";
    }

    private static String shorten(String s, int max) {
        if (s == null) {
            return "";
        }
        String t = QuoteParser.clean(s);
        return t.length() <= max ? t : t.substring(0, max) + "…";
    }
}
