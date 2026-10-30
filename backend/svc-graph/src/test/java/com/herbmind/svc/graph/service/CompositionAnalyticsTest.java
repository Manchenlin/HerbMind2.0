package com.herbmind.svc.graph.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.herbmind.svc.graph.dto.FormulaGraph;
import com.herbmind.svc.graph.dto.GraphMap;
import com.herbmind.svc.graph.repo.CompositionRepository.HerbRow;

/**
 * 药味组成的确定性计算（设计红线五：能用规则算的不交给大模型）。
 *
 * 重点钉三件事：Jaccard 公式与排序、脏药名的判定边界、地图布局的**可复现性**
 * （契约 §15.5 要求同一 version 反复请求必须同一张图）。
 */
class CompositionAnalyticsTest {

    private static HerbRow row(String fid, String herb, int seq) {
        return new HerbRow(fid, herb, seq, null, null, null);
    }

    private static Map<String, Set<String>> setsOf(HerbRow... rows) {
        return CompositionAnalytics.herbSets(List.of(rows));
    }

    @Test
    @DisplayName("jaccard：|A∩B| / |A∪B|，空集为 0")
    void jaccardBasic() {
        assertEquals(0.5, CompositionAnalytics.jaccard(Set.of("麻黄", "桂枝", "甘草"),
                Set.of("桂枝", "甘草", "杏仁")), 1e-9);
        assertEquals(1.0, CompositionAnalytics.jaccard(Set.of("麻黄"), Set.of("麻黄")), 1e-9);
        assertEquals(0.0, CompositionAnalytics.jaccard(Set.of("麻黄"), Set.of("桂枝")), 1e-9);
        assertEquals(0.0, CompositionAnalytics.jaccard(Set.of(), Set.of("桂枝")), 1e-9);
    }

    @Test
    @DisplayName("herbSets：按方剂去重分组")
    void herbSetsGrouping() {
        Map<String, Set<String>> sets = setsOf(
                row("f_1", "麻黄", 1), row("f_1", "桂枝", 2), row("f_1", "麻黄", 3),
                row("f_2", "桂枝", 1));
        assertEquals(Set.of("麻黄", "桂枝"), sets.get("f_1"));
        assertEquals(Set.of("桂枝"), sets.get("f_2"));
    }

    @Test
    @DisplayName("relatedFormulas：交集为空不返回，按 Jaccard 降序，最多 5 条")
    void relatedFormulasRanking() {
        Map<String, Set<String>> sets = setsOf(
                row("f_1", "麻黄", 1), row("f_1", "桂枝", 2), row("f_1", "甘草", 3), row("f_1", "杏仁", 4),
                // 2/4 交集 → 0.333…
                row("f_2", "麻黄", 1), row("f_2", "桂枝", 2), row("f_2", "石膏", 3), row("f_2", "生姜", 4),
                // 3 味交集 / 6 味并集 → 0.5
                row("f_3", "麻黄", 1), row("f_3", "桂枝", 2), row("f_3", "甘草", 3), row("f_3", "大枣", 4),
                row("f_3", "生姜", 5),
                // 完全不相交 → 不应出现
                row("f_4", "黄连", 1), row("f_4", "黄芩", 2));
        Map<String, String> names = Map.of("f_1", "麻黄汤", "f_2", "某汤", "f_3", "另一汤", "f_4", "黄连汤");

        List<FormulaGraph.RelatedFormula> related =
                CompositionAnalytics.relatedFormulas("f_1", sets, names);

        assertEquals(2, related.size());
        assertEquals("f_3", related.get(0).id());
        assertEquals(0.5, related.get(0).jaccard(), 1e-9);
        // 交集药味按汉字码位排序（TreeSet 自然序）：桂 < 甘 < 麻
        assertEquals(List.of("桂枝", "甘草", "麻黄"), related.get(0).sharedHerbs());
        assertEquals("f_2", related.get(1).id());
        assertEquals(0.3333, related.get(1).jaccard(), 1e-9);

        // 自身不出现在关联列表里
        assertTrue(related.stream().noneMatch(r -> r.id().equals("f_1")));
    }

    @Test
    @DisplayName("relatedFormulas：该方没有药味时返回空")
    void relatedFormulasEmptyTarget() {
        Map<String, Set<String>> sets = setsOf(row("f_2", "桂枝", 1));
        assertTrue(CompositionAnalytics.relatedFormulas("f_1", sets, Map.of("f_2", "某汤")).isEmpty());
    }

    @Test
    @DisplayName("isDirtyHerbName：正名不误伤，解析残留要抓到")
    void dirtyHerbNames() {
        // 干净
        assertFalse(CompositionAnalytics.isDirtyHerbName("麻黄"));
        assertFalse(CompositionAnalytics.isDirtyHerbName("甘草"));
        assertFalse(CompositionAnalytics.isDirtyHerbName("甘李根白皮"));
        assertFalse(CompositionAnalytics.isDirtyHerbName("升麻"));   // 含"升"但只有 2 字
        // 脏：[实核 2026-10-28] 库里真实出现过的形态
        assertTrue(CompositionAnalytics.isDirtyHerbName("甘草(炙"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("炙)杏仁"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("麻黄(去节"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("青子芩钱半至"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("麻黄芍药黄芪"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("芎劳各一斤"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("甘草如指大"));
        assertTrue(CompositionAnalytics.isDirtyHerbName("1"));
        assertTrue(CompositionAnalytics.isDirtyHerbName(""));
    }

    @Test
    @DisplayName("isHerbsIncomplete：无药味或含脏药名都算不完整")
    void herbsIncomplete() {
        assertTrue(CompositionAnalytics.isHerbsIncomplete(List.of()));
        assertTrue(CompositionAnalytics.isHerbsIncomplete(null));
        assertFalse(CompositionAnalytics.isHerbsIncomplete(List.of(row("f_1", "麻黄", 1), row("f_1", "桂枝", 2))));
        assertTrue(CompositionAnalytics.isHerbsIncomplete(
                List.of(row("f_1", "麻黄", 1), row("f_1", "麻黄(去节", 2))));
    }

    @Test
    @DisplayName("layout：同输入必须同输出，坐标落在 0~1")
    void layoutIsDeterministic() {
        List<HerbRow> rows = new ArrayList<>();
        List<String> ids = new ArrayList<>();
        for (int i = 1; i <= 12; i++) {
            String id = "f_" + i;
            ids.add(id);
            rows.add(row(id, "甘草", 1));
            // 每首方与相邻号码的方共享药味，制造分簇
            rows.add(row(id, "药" + (i % 4), 2));
        }
        Map<String, Set<String>> sets = CompositionAnalytics.herbSets(rows);

        double[][] first = CompositionAnalytics.layout(ids, sets);
        double[][] second = CompositionAnalytics.layout(ids, sets);

        assertEquals(ids.size(), first.length);
        for (int i = 0; i < first.length; i++) {
            assertEquals(first[i][0], second[i][0], 0.0, "同输入第二次布局必须逐位相同");
            assertEquals(first[i][1], second[i][1], 0.0);
            assertTrue(first[i][0] >= 0.0 && first[i][0] <= 1.0, "x 必须归一化到 0~1");
            assertTrue(first[i][1] >= 0.0 && first[i][1] <= 1.0, "y 必须归一化到 0~1");
        }
    }

    @Test
    @DisplayName("layout：单点放中心，空输入返回空数组")
    void layoutDegenerate() {
        assertEquals(0, CompositionAnalytics.layout(List.of(), Map.of()).length);

        double[][] one = CompositionAnalytics.layout(List.of("f_1"), setsOf(row("f_1", "麻黄", 1)));
        assertEquals(0.5, one[0][0], 1e-9);
        assertEquals(0.5, one[0][1], 1e-9);
    }

    @Test
    @DisplayName("clusters：药味高度重叠的方落在同一簇，互不相干的分开")
    void clustersByJaccard() {
        Map<String, Set<String>> sets = setsOf(
                row("f_1", "麻黄", 1), row("f_1", "桂枝", 2),
                row("f_2", "麻黄", 1), row("f_2", "桂枝", 2),   // 与 f_1 完全相同 → 0.5 以上
                row("f_3", "黄连", 1), row("f_3", "黄芩", 2));  // 与 f_1 无交集
        List<String> ids = List.of("f_1", "f_2", "f_3");

        int[] labels = CompositionAnalytics.clusters(ids, sets);

        assertEquals(labels[0], labels[1]);
        assertTrue(labels[0] != labels[2]);
    }

    @Test
    @DisplayName("clusters：连通分量的“串联”不会把一大片并成一簇（超比例就升档再拆）")
    void clustersSplitOversizedComponent() {
        // 10 首方首尾相接：相邻共享 2 味（Jaccard 0.5），隔一首 0.2
        // 固定阈值 0.5 时单链接会把 10 首串成 1 簇，占比 100% —— 颜色就没信息量了
        List<HerbRow> rows = new ArrayList<>();
        List<String> ids = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            String id = "f_" + (i + 1);
            ids.add(id);
            rows.add(row(id, "药" + i, 1));
            rows.add(row(id, "药" + (i + 1), 2));
            rows.add(row(id, "药" + (i + 2), 3));
        }
        Map<String, Set<String>> sets = CompositionAnalytics.herbSets(rows);

        int[] labels = CompositionAnalytics.clusters(ids, sets);

        int[] size = new int[ids.size() + 1];
        for (int l : labels) {
            size[l]++;
        }
        int largest = 0;
        for (int s : size) {
            largest = Math.max(largest, s);
        }
        assertTrue(largest <= 6, "最大的簇最多 6 个点（n=10 时 max(6, ceil(10*0.15))），实际 " + largest);

        // 升档后（0.6）相邻也不达标，于是各成一簇
        assertEquals(10, (int) java.util.Arrays.stream(labels).distinct().count());

        // 可复现
        assertEquals(java.util.Arrays.toString(labels),
                java.util.Arrays.toString(CompositionAnalytics.clusters(ids, sets)));
    }

    @Test
    @DisplayName("version：同数据同版本，数据一变版本就变")
    void versionFingerprint() {
        Map<String, Set<String>> sets = setsOf(row("f_1", "麻黄", 1), row("f_2", "桂枝", 1));
        List<String> ids = List.of("f_1", "f_2");

        String v1 = CompositionAnalytics.version(ids, sets);
        String v2 = CompositionAnalytics.version(ids, sets);
        assertEquals(v1, v2);
        assertTrue(v1.startsWith("composition:v1:"));

        Map<String, Set<String>> changed = new LinkedHashMap<>(sets);
        changed.put("f_2", Set.of("桂枝", "杏仁"));
        assertFalse(v1.equals(CompositionAnalytics.version(ids, changed)));
    }

    @Test
    @DisplayName("points：点集 id/name/cluster 与输入一致，id 不暴露 elementId")
    void pointsShape() {
        Map<String, Set<String>> sets = setsOf(row("f_1", "麻黄", 1), row("f_2", "桂枝", 1));
        List<GraphMap.Point> points = CompositionAnalytics.points(
                List.of("f_1", "f_2"), Map.of("f_1", "麻黄汤", "f_2", "桂枝汤"), sets);

        assertEquals(2, points.size());
        assertEquals("f_1", points.get(0).id());
        assertEquals("麻黄汤", points.get(0).name());
        assertEquals("Formula", points.get(0).label());
        assertTrue(points.get(0).cluster().startsWith("c"));
    }
}
