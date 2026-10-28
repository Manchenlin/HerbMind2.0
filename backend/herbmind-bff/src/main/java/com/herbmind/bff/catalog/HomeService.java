package com.herbmind.bff.catalog;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.herbmind.contract.catalog.BookVO;
import com.herbmind.contract.catalog.CatalogStatsVO;
import com.herbmind.contract.catalog.CatalogClient;
import com.herbmind.contract.catalog.FormulaVO;
import com.herbmind.contract.catalog.GraphPreviewVO;
import com.herbmind.contract.search.SearchClient;
import com.herbmind.contract.search.SearchHitVO;

/**
 * 首页编排：catalog（统计 / 书架 / 今日方证）+ 图谱预览。
 *
 * 设计：每个分区独立降级（try/catch）。某个 svc 挂了只影响那一块，首页仍然可看，
 * 并把降级信息放进 degraded，前端给出「部分数据不可用」提示。
 */
@Service
public class HomeService {

    private static final Logger log = LoggerFactory.getLogger(HomeService.class);

    private static final List<String> HOT_KEYWORDS = List.of(
            "无汗而喘", "太阳中风", "项背强几几", "脉浮紧", "小柴胡汤", "桂枝汤");

    private final CatalogClient catalog;
    private final SearchClient search;

    public HomeService(CatalogClient catalog, SearchClient search) {
        this.catalog = catalog;
        this.search = search;
    }

    public HomeVO home() {
        List<String> degraded = new ArrayList<>();

        CatalogStatsVO stats = safe(catalog::stats, "stats", degraded);
        List<BookVO> books = safe(catalog::books, "books", degraded);
        FormulaVO today = safe(() -> catalog.daily(""), "today", degraded);
        GraphPreviewVO graph = today == null ? null
                : safe(() -> catalog.graphPreview(today.id()), "graph", degraded);
        List<SearchHitVO> hotHits = safe(
                () -> search.search(HOT_KEYWORDS.get(0), "", "", "", "", 1, 4).list(),
                "search", degraded);

        return new HomeVO(stats, books, today, graph,
                "catalog-preview", HOT_KEYWORDS, hotHits == null ? List.of() : hotHits, degraded);
    }

    private <T> T safe(Supplier<T> supplier, String name, List<String> degraded) {
        try {
            return supplier.get();
        } catch (Exception e) {
            log.warn("首页分区 [{}] 降级：{}", name, e.getMessage());
            degraded.add(name);
            return null;
        }
    }
}
