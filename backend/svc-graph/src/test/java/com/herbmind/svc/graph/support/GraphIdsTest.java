package com.herbmind.svc.graph.support;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 对外 ID 口径（09 契约 §15 硬约定）：方剂 f_*、药味 h_*，绝不给前端 elementId。
 *
 * 这组断言的意义：一旦有人把 neo4j elementId 当成对外 ID 传出去，收藏/分享会随重建库失效，
 * 而这种问题只在换库后才暴露，测试里先钉死。
 */
class GraphIdsTest {

    @Test
    @DisplayName("formulaId：已带前缀保持原样，裸 id 补 f_，空值返回 null")
    void formulaIdNormalize() {
        assertEquals("f_1", GraphIds.formulaId("f_1"));
        assertEquals("f_1", GraphIds.formulaId("1"));
        assertEquals("f_12", GraphIds.formulaId(" 12 "));
        assertNull(GraphIds.formulaId(null));
        assertNull(GraphIds.formulaId("   "));
    }

    @Test
    @DisplayName("herbId：药名前面拼 h_")
    void herbIdPrefix() {
        assertEquals("h_麻黄", GraphIds.herbId("麻黄"));
        assertEquals("h_麻黄", GraphIds.herbId(" 麻黄 "));
        assertNull(GraphIds.herbId(""));
        assertNull(GraphIds.herbId(null));
    }

    @Test
    @DisplayName("strip：把业务 ID 还原成库内写法")
    void stripPrefix() {
        assertEquals("1", GraphIds.stripFormula("f_1"));
        assertEquals("1", GraphIds.stripFormula("1"));
        assertEquals("麻黄", GraphIds.stripHerb("h_麻黄"));
        assertEquals("麻黄", GraphIds.stripHerb("麻黄"));
    }

    @Test
    @DisplayName("compareById：按数字后缀排序，f_9 在 f_10 之前")
    void compareByIdIsNumeric() {
        List<String> ids = new ArrayList<>(List.of("f_10", "f_9", "f_100", "f_1"));
        ids.sort(GraphIds::compareById);
        assertEquals(List.of("f_1", "f_9", "f_10", "f_100"), ids);

        // 非数字后缀（药味）退回字符串比较，不抛异常
        assertEquals("h_麻黄".compareTo("h_桂枝"), GraphIds.compareById("h_麻黄", "h_桂枝"));
    }

    @Test
    @DisplayName("前缀判定")
    void prefixCheck() {
        assertTrue(GraphIds.isFormulaId("f_1"));
        assertFalse(GraphIds.isFormulaId("h_麻黄"));
        assertTrue(GraphIds.isHerbId("h_麻黄"));
        assertFalse(GraphIds.isHerbId(null));
    }
}
