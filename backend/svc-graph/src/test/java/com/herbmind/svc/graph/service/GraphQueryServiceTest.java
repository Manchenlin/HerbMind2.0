package com.herbmind.svc.graph.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.herbmind.svc.graph.dto.FormulaGraph;
import com.herbmind.svc.graph.exception.GraphEntityNotFoundException;
import com.herbmind.svc.graph.repo.CompositionRepository;
import com.herbmind.svc.graph.repo.CompositionRepository.FormulaRow;
import com.herbmind.svc.graph.repo.CompositionRepository.HerbRow;

/**
 * /formula/{id} 的入参解析：ID、裸数字、方名三种写法，以及**重名不允许瞎猜**。
 *
 * 只测 formulaGraph —— 它全部数据来自 PG，可以塞桩数据；其余端点要 Neo4j，留给实打验证。
 */
class GraphQueryServiceTest {

    private static final List<FormulaRow> FORMULAS = List.of(
            new FormulaRow("f_1", "麻黄汤", "", "恶风寒、发热…", null, null),
            new FormulaRow("f_2", "葛根汤", null, null, null, null),
            new FormulaRow("f_3", "大青龙汤", null, null, null, null),
            new FormulaRow("f_128", "葛根汤", null, null, null, null));

    private static final List<HerbRow> HERBS = List.of(
            new HerbRow("f_1", "麻黄", 1, null, null, null),
            new HerbRow("f_1", "桂枝", 2, null, null, null),
            new HerbRow("f_1", "杏仁", 3, null, null, null),
            new HerbRow("f_1", "甘草", 4, null, null, null),
            new HerbRow("f_2", "麻黄", 1, null, null, null),
            new HerbRow("f_2", "桂枝", 2, null, null, null),
            new HerbRow("f_128", "麻黄", 1, null, null, null),
            new HerbRow("f_3", "麻黄", 1, null, null, null),
            new HerbRow("f_3", "桂枝", 2, null, null, null),
            new HerbRow("f_3", "杏仁", 3, null, null, null),
            new HerbRow("f_3", "甘草", 4, null, null, null),
            new HerbRow("f_3", "石膏", 5, null, null, null));

    /** 桩仓储：只覆盖两个只读方法，不连库（构造传 null 的 JdbcTemplate 也不会被用到）。 */
    private static CompositionRepository stubRepository() {
        return new CompositionRepository(null) {
            @Override
            public List<FormulaRow> formulas() {
                return FORMULAS;
            }

            @Override
            public List<HerbRow> herbRows() {
                return HERBS;
            }
        };
    }

    private final GraphQueryService service = new GraphQueryService(null, stubRepository());

    @Test
    @DisplayName("按 ID 查：f_1")
    void byId() {
        FormulaGraph g = service.formulaGraph("f_1");
        assertEquals("f_1", g.center().id());
        assertEquals("麻黄汤", g.center().name());
        assertEquals(4, g.herbs().size());
        // 药味按库内 seq 升序，ID 用 h_ 前缀
        assertEquals(List.of("h_麻黄", "h_桂枝", "h_杏仁", "h_甘草"),
                g.herbs().stream().map(FormulaGraph.Herb::id).toList());
        assertFalse(g.herbsIncomplete());
        assertTrue(g.notice().contains("不构成处方建议"));
    }

    @Test
    @DisplayName("裸数字 1 等价于 f_1")
    void byBareNumber() {
        assertEquals("f_1", service.formulaGraph("1").center().id());
    }

    @Test
    @DisplayName("按方名查：麻黄汤 → f_1")
    void byName() {
        FormulaGraph g = service.formulaGraph(" 麻黄汤 ");
        assertEquals("f_1", g.center().id());
    }

    @Test
    @DisplayName("关联方按 Jaccard 降序：多一味石膏的大青龙汤最靠前（4/5 = 0.8）")
    void relatedOrder() {
        FormulaGraph g = service.formulaGraph("f_1");
        assertEquals("f_3", g.relatedFormulas().get(0).id());
        assertEquals(0.8, g.relatedFormulas().get(0).jaccard(), 1e-9);
    }

    @Test
    @DisplayName("方名重名 → 4000（IllegalArgumentException）并给出候选 ID，不许瞎猜")
    void duplicateNameRejected() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> service.formulaGraph("葛根汤"));
        assertTrue(e.getMessage().contains("f_2"), "提示里要带候选 ID：" + e.getMessage());
        assertTrue(e.getMessage().contains("f_128"), "提示里要带候选 ID：" + e.getMessage());
    }

    @Test
    @DisplayName("ID 和方名都不存在 → 4040")
    void notFound() {
        assertThrows(GraphEntityNotFoundException.class, () -> service.formulaGraph("不存在的方"));
        assertThrows(GraphEntityNotFoundException.class, () -> service.formulaGraph("f_9999"));
    }
}
