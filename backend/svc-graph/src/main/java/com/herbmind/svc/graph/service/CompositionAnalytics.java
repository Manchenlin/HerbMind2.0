package com.herbmind.svc.graph.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Pattern;

import com.herbmind.svc.graph.dto.FormulaGraph;
import com.herbmind.svc.graph.dto.GraphMap;
import com.herbmind.svc.graph.repo.CompositionRepository.HerbRow;
import com.herbmind.svc.graph.support.GraphIds;

/**
 * 药味组成的确定性计算：Jaccard、脏药名判定、相似度地图布局、数据指纹。
 *
 * 全部是纯函数（不碰 Neo4j / PG），便于单测。
 * 设计红线五：能用规则算的不交给大模型 —— 组成比对、集合差集、Jaccard、频次一律这里算。
 */
public final class CompositionAnalytics {

    /** 免责声明（09 契约 §15.3 notice）。 */
    public static final String NOTICE =
            "仅比对药味组成，不比对剂量与配伍关系；「组成相同」不等于「是同一方」，不构成处方建议。";

    /** 一期唯一允许的距离口径：药味 Jaccard（不提供"功效相似"这类推断口径）。 */
    public static final String METRIC_COMPOSITION = "composition";

    /** 关联方返回条数上限（契约 §15.3）。 */
    public static final int RELATED_TOP_N = 5;

    /**
     * 地图配色分组的阈值阶梯：先用 0.5（药味明显重合），簇太大就逐级升到 0.9。
     * 升档的意义见 {@link #clusters}：连通分量会"串联"，一档切不出可用的颜色。
     */
    private static final double[] CLUSTER_THRESHOLDS = {0.5, 0.6, 0.7, 0.8, 0.9};

    /** 单簇最多占点数的比例；超出的簇升档再拆。 */
    private static final double CLUSTER_MAX_SHARE = 0.15;

    /** 单簇至少允许的绝对点数：点很少时不要拆得过碎（否则每个点一个颜色）。 */
    private static final int CLUSTER_MIN_MAX_SIZE = 6;

    /**
     * 脏药名残留词：剂量/炮制/接排残留。
     * 只对长度 ≥ 4 的名字启用 —— 「升麻」「羌活」这类 2 字正名不会被误伤。
     */
    private static final List<String> RESIDUE_TOKENS =
            List.of("等分", "各", "钱", "两", "斤", "枚", "张", "至", "如", "加", "或");

    /** 纯汉字校验：括号、句号、书名号、数字一律视为解析残留。 */
    private static final Pattern HAN_ONLY = Pattern.compile("^[\\u4e00-\\u9fa5]+$");

    /**
     * 库内干净药名最长 5 字（[实核 2026-10-28] 如「甘李根白皮」），6 字及以上全部是残留
     * （如「青子芩钱半至」「大黄三两大枣」「麻黄芍药黄芪」）。
     */
    private static final int MAX_CLEAN_HERB_NAME_LEN = 5;

    /**
     * 幂迭代轮数。刻意用**固定轮数**而不是"收敛即停"：收敛阈值会让不同数据迭代次数不同，
     * 反而给可复现性加了变量；固定轮数 + LCG 定值初值 = 同输入逐位同输出。
     */
    private static final int PCOA_POWER_ITERATIONS = 200;

    /** kNN 细化：迭数、初始温度、每个点保留的最相似邻居数（数值来自真实 245 首方的原型调参）。 */
    private static final int REFINE_ITERATIONS = 80;
    private static final double REFINE_START_TEMP = 0.02;
    private static final int KNN_K = 3;

    private CompositionAnalytics() {
    }

    // ------------------------------------------------------------------ 药味集合

    /** 按方剂分组的药味行（保留 seq 顺序）。 */
    public static Map<String, List<HerbRow>> rowsByFormula(Collection<HerbRow> rows) {
        Map<String, List<HerbRow>> grouped = new LinkedHashMap<>();
        for (HerbRow r : rows) {
            grouped.computeIfAbsent(r.formulaId(), k -> new ArrayList<>()).add(r);
        }
        return grouped;
    }

    /** 按方剂分组的**去重药名集合**（Jaccard 用）。 */
    public static Map<String, Set<String>> herbSets(Collection<HerbRow> rows) {
        Map<String, Set<String>> sets = new LinkedHashMap<>();
        for (HerbRow r : rows) {
            if (r.herbName() == null || r.herbName().isBlank()) {
                continue;
            }
            sets.computeIfAbsent(r.formulaId(), k -> new LinkedHashSet<>()).add(r.herbName().trim());
        }
        return sets;
    }

    /**
     * 疑似解析残留的药名。
     *
     * 命中任一即视为脏：含非汉字字符 / 长度 ≥ 6 / 长度 ≥ 4 且含剂量残留词。
     * 这是**启发式**，只用来给前端一个「药味可能不完整」的提示，不参与任何功效判断。
     */
    public static boolean isDirtyHerbName(String name) {
        if (name == null || name.isBlank()) {
            return true;
        }
        String s = name.trim();
        if (!HAN_ONLY.matcher(s).matches()) {
            return true;
        }
        if (s.length() > MAX_CLEAN_HERB_NAME_LEN) {
            return true;
        }
        if (s.length() >= 4) {
            for (String token : RESIDUE_TOKENS) {
                if (s.contains(token)) {
                    return true;
                }
            }
        }
        return false;
    }

    /** 药味是否缺失或不干净：0 条药味，或任一药名命中脏规则。 */
    public static boolean isHerbsIncomplete(List<HerbRow> rows) {
        if (rows == null || rows.isEmpty()) {
            return true;
        }
        for (HerbRow r : rows) {
            if (isDirtyHerbName(r.herbName())) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------ Jaccard

    public static double jaccard(Set<String> a, Set<String> b) {
        if (a == null || b == null || a.isEmpty() || b.isEmpty()) {
            return 0.0;
        }
        Set<String> small = a.size() <= b.size() ? a : b;
        Set<String> large = small == a ? b : a;
        int inter = 0;
        for (String s : small) {
            if (large.contains(s)) {
                inter++;
            }
        }
        int union = a.size() + b.size() - inter;
        return union == 0 ? 0.0 : (double) inter / union;
    }

    /**
     * 与该方药味交集最大的成方（按 Jaccard 降序，最多 {@value #RELATED_TOP_N} 条）。
     *
     * 规则明确：**只看药味集合**（不看剂量、不看主治），交集为空的不返回。
     * 前端必须标注「组成相近 ≠ 同一方」。
     */
    public static List<FormulaGraph.RelatedFormula> relatedFormulas(
            String targetId,
            Map<String, Set<String>> sets,
            Map<String, String> names) {
        Set<String> target = sets.get(targetId);
        if (target == null || target.isEmpty()) {
            return List.of();
        }
        List<Row> scored = new ArrayList<>();
        for (Map.Entry<String, Set<String>> e : sets.entrySet()) {
            if (e.getKey().equals(targetId) || e.getValue().isEmpty()) {
                continue;
            }
            double j = jaccard(target, e.getValue());
            if (j <= 0.0) {
                continue;
            }
            Set<String> shared = new TreeSet<>(target);
            shared.retainAll(e.getValue());
            scored.add(new Row(e.getKey(), j, List.copyOf(shared)));
        }
        scored.sort((x, y) -> {
            int c = Double.compare(y.jaccard, x.jaccard);
            return c != 0 ? c : GraphIds.compareById(x.id, y.id);
        });
        List<FormulaGraph.RelatedFormula> out = new ArrayList<>();
        for (int i = 0; i < Math.min(RELATED_TOP_N, scored.size()); i++) {
            Row r = scored.get(i);
            out.add(new FormulaGraph.RelatedFormula(r.id, names.getOrDefault(r.id, r.id),
                    r.shared, round(r.jaccard, 4)));
        }
        return out;
    }

    private record Row(String id, double jaccard, List<String> shared) {
    }

    // ------------------------------------------------------------------ 相似度地图

    /**
     * 确定性布局：**PCoA（经典多维标度）定全局 + kNN 力导向做局部细化**。
     *
     * 为什么不是纯力导向：实测纯 FR 力导向在 245 首方的真实数据上会把 90% 的点挤在中间
     * 0.37~0.57 的一条窄带里（少数孤立点把 min-max 撑开），页面看起来就是一团；
     * 只用 PCoA 则全局摊得开（std≈0.28）但"最像的几首"挨得不够近（近邻距离比 0.60）。
     * 两者叠加后 std≈0.30、近邻距离比≈0.39，既摊得开又保住了局部相似结构。
     *
     * 确定性来自三处，全部不依赖随机数：
     * 1. PCoA 的特征向量用**幂迭代 + LCG 定值初值**求（不用特征分解库，避免多解与顺序抖动）；
     * 2. 特征向量符号统一规定为「绝对值最大的分量取正」；
     * 3. 细化固定 80 轮、固定降温曲线；归一化用 1%~99% 分位数裁尾（防孤立点压扁其余点）。
     *
     * **这不是 UMAP/PCA 那类可解读的降维**：它只保证同输入同输出、近的更像，
     * 坐标轴没有语义，前端不要拿 x/y 做任何数值解释。
     *
     * @return 长度 = ids.size() 的坐标数组，元素为 {x, y} ∈ [0,1]
     */
    public static double[][] layout(List<String> ids, Map<String, Set<String>> sets) {
        int n = ids.size();
        if (n == 0) {
            return new double[0][2];
        }
        if (n == 1) {
            return new double[][] {{0.5, 0.5}};
        }

        double[][] sim = similarityMatrix(ids, sets);
        double[][] pos = pcoa(sim);
        refineByKnn(pos, sim);
        return robustNormalize(pos);
    }

    /** 药味 Jaccard 相似度矩阵，对角线为 1。 */
    private static double[][] similarityMatrix(List<String> ids, Map<String, Set<String>> sets) {
        int n = ids.size();
        double[][] sim = new double[n][n];
        for (int i = 0; i < n; i++) {
            sim[i][i] = 1.0;
            for (int j = i + 1; j < n; j++) {
                double s = jaccard(sets.get(ids.get(i)), sets.get(ids.get(j)));
                sim[i][j] = s;
                sim[j][i] = s;
            }
        }
        return sim;
    }

    /**
     * PCoA：对 (1 - Jaccard) 距离矩阵做双中心化得到 B，取 |λ| 最大的两个特征向量当坐标。
     * 特征向量用幂迭代求（B 是 n×n 稠密阵，n≤500 时幂迭代比完整特征分解快一个量级）。
     */
    private static double[][] pcoa(double[][] sim) {
        int n = sim.length;
        double[][] d2 = new double[n][n];
        double[] rowMean = new double[n];
        double grand = 0;
        for (int i = 0; i < n; i++) {
            double sum = 0;
            for (int j = 0; j < n; j++) {
                double d = 1.0 - sim[i][j];
                d2[i][j] = d * d;
                sum += d2[i][j];
            }
            rowMean[i] = sum / n;
            grand += sum;
        }
        grand /= (double) n * n;

        double[][] b = new double[n][n];
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                b[i][j] = -0.5 * (d2[i][j] - rowMean[i] - rowMean[j] + grand);
            }
        }

        double[] v1 = powerIteration(b, null, 0.0);
        double lambda1 = rayleigh(b, v1);
        double[] v2 = powerIteration(b, v1, lambda1);
        double lambda2 = rayleigh(b, v2);

        double scale1 = Math.sqrt(Math.abs(lambda1));
        double scale2 = Math.sqrt(Math.abs(lambda2));
        double[][] pos = new double[n][2];
        for (int i = 0; i < n; i++) {
            pos[i][0] = v1[i] * scale1;
            pos[i][1] = v2[i] * scale2;
        }
        return pos;
    }

    /**
     * 幂迭代求主特征向量。给了 deflateFrom 时先把该方向的投影减掉，用来求第二主方向。
     * 初值用 LCG 生成（整数运算，跨 JVM 逐位一致），符号按「绝对值最大分量取正」固定。
     */
    private static double[] powerIteration(double[][] b, double[] deflateFrom, double deflateValue) {
        int n = b.length;
        double[] v = lcgVector(n);
        if (deflateFrom != null) {
            orthonormalize(v, deflateFrom);
        }
        normalizeVector(v);

        for (int iter = 0; iter < PCOA_POWER_ITERATIONS; iter++) {
            double[] next = new double[n];
            for (int i = 0; i < n; i++) {
                double[] row = b[i];
                double sum = 0;
                for (int j = 0; j < n; j++) {
                    sum += row[j] * v[j];
                }
                next[i] = sum;
            }
            if (deflateFrom != null) {
                double dot = dot(deflateFrom, v);
                for (int i = 0; i < n; i++) {
                    next[i] -= deflateValue * deflateFrom[i] * dot;
                }
            }
            double len = normalizeVector(next);
            if (len < 1e-12) {
                break;
            }
            v = next;
        }

        // 符号统一：绝对值最大的分量取正，保证同一份数据永远得到同一组坐标
        int pivot = 0;
        for (int i = 1; i < n; i++) {
            if (Math.abs(v[i]) > Math.abs(v[pivot])) {
                pivot = i;
            }
        }
        if (v[pivot] < 0) {
            for (int i = 0; i < n; i++) {
                v[i] = -v[i];
            }
        }
        return v;
    }

    private static double[] lcgVector(int n) {
        long state = 0x2545F4914F6CDD1DL;
        double[] v = new double[n];
        for (int i = 0; i < n; i++) {
            state = state * 6364136223846793005L + 1442695040888963407L;
            v[i] = ((state >>> 11) / (double) (1L << 53)) - 0.5;
        }
        return v;
    }

    private static void orthonormalize(double[] v, double[] basis) {
        double dot = dot(v, basis);
        for (int i = 0; i < v.length; i++) {
            v[i] -= dot * basis[i];
        }
    }

    private static double dot(double[] a, double[] b) {
        double sum = 0;
        for (int i = 0; i < a.length; i++) {
            sum += a[i] * b[i];
        }
        return sum;
    }

    private static double normalizeVector(double[] v) {
        double sum = 0;
        for (double x : v) {
            sum += x * x;
        }
        double len = Math.sqrt(sum);
        if (len > 1e-12) {
            for (int i = 0; i < v.length; i++) {
                v[i] /= len;
            }
        }
        return len;
    }

    private static double rayleigh(double[][] b, double[] v) {
        double sum = 0;
        for (int i = 0; i < b.length; i++) {
            double[] row = b[i];
            double acc = 0;
            for (int j = 0; j < b.length; j++) {
                acc += row[j] * v[j];
            }
            sum += acc * v[i];
        }
        return sum;
    }

    /**
     * 局部细化：只对每个点最相似的 {@value #KNN_K} 个邻居施加引力，其余全靠 1/d 斥力。
     * 这样相似簇内部会被压紧，同时簇与簇之间保持 PCoA 给的间距。
     */
    private static void refineByKnn(double[][] pos, double[][] sim) {
        int n = pos.length;
        double[][] weight = new double[n][n];
        for (int i = 0; i < n; i++) {
            for (int pick = 0; pick < KNN_K; pick++) {
                int best = -1;
                double bestSim = 0.0;
                for (int j = 0; j < n; j++) {
                    if (j == i || sim[i][j] <= 0.0) {
                        continue;
                    }
                    // 已选过的邻居（用 weight 标记）跳过，避免重复占位
                    if (weight[i][j] > 0.0) {
                        continue;
                    }
                    if (sim[i][j] > bestSim) {
                        bestSim = sim[i][j];
                        best = j;
                    }
                }
                if (best < 0) {
                    break;
                }
                weight[i][best] = bestSim;
                weight[best][i] = bestSim;
            }
        }

        // 先把 PCoA 坐标压到单位跨度，力的大小才有统一量纲
        double minX = Double.MAX_VALUE;
        double maxX = -Double.MAX_VALUE;
        double minY = Double.MAX_VALUE;
        double maxY = -Double.MAX_VALUE;
        for (double[] p : pos) {
            minX = Math.min(minX, p[0]);
            maxX = Math.max(maxX, p[0]);
            minY = Math.min(minY, p[1]);
            maxY = Math.max(maxY, p[1]);
        }
        double span = Math.max(Math.max(maxX - minX, maxY - minY), 1e-9);
        for (double[] p : pos) {
            p[0] = (p[0] - minX) / span;
            p[1] = (p[1] - minY) / span;
        }

        double k = 1.0 / Math.sqrt(n);
        double temp = REFINE_START_TEMP;
        double cooling = Math.pow(0.001 / temp, 1.0 / REFINE_ITERATIONS);
        double[][] disp = new double[n][2];

        for (int iter = 0; iter < REFINE_ITERATIONS; iter++) {
            for (int i = 0; i < n; i++) {
                disp[i][0] = 0;
                disp[i][1] = 0;
            }
            for (int i = 0; i < n; i++) {
                for (int j = i + 1; j < n; j++) {
                    double dx = pos[i][0] - pos[j][0];
                    double dy = pos[i][1] - pos[j][1];
                    double dist = Math.max(Math.hypot(dx, dy), 1e-4);
                    double f = k * k / dist - weight[i][j] * dist / k;
                    double ux = dx / dist;
                    double uy = dy / dist;
                    disp[i][0] += f * ux;
                    disp[i][1] += f * uy;
                    disp[j][0] -= f * ux;
                    disp[j][1] -= f * uy;
                }
            }
            for (int i = 0; i < n; i++) {
                double len = Math.hypot(disp[i][0], disp[i][1]);
                if (len > 1e-9) {
                    double scale = Math.min(len, temp) / len;
                    pos[i][0] += disp[i][0] * scale;
                    pos[i][1] += disp[i][1] * scale;
                }
            }
            temp *= cooling;
        }
    }

    /**
     * 逐轴分位数裁尾后压到 [0,1]：孤立点会落在 0 或 1 边界上被裁平，
     * 但不会再把它压住的那一大片点挤成一个点。
     */
    private static double[][] robustNormalize(double[][] pos) {
        int n = pos.length;
        double[][] out = new double[n][2];
        for (int axis = 0; axis < 2; axis++) {
            double[] values = new double[n];
            for (int i = 0; i < n; i++) {
                values[i] = pos[i][axis];
            }
            double[] sorted = values.clone();
            Arrays.sort(sorted);
            double lo = quantile(sorted, 0.01);
            double hi = quantile(sorted, 0.99);
            if (hi - lo < 1e-9) {
                for (int i = 0; i < n; i++) {
                    out[i][axis] = 0.5;
                }
                continue;
            }
            for (int i = 0; i < n; i++) {
                double v = (values[i] - lo) / (hi - lo);
                out[i][axis] = round(Math.min(1.0, Math.max(0.0, v)), 4);
            }
        }
        return out;
    }

    private static double quantile(double[] sorted, double q) {
        if (sorted.length == 0) {
            return 0.0;
        }
        double pos = q * (sorted.length - 1);
        int lower = (int) Math.floor(pos);
        int upper = Math.min(lower + 1, sorted.length - 1);
        double frac = pos - lower;
        return sorted[lower] * (1 - frac) + sorted[upper] * frac;
    }

    /**
     * 确定性配色分组：药味 Jaccard 达到阈值的方剂连成同一簇（并查集），簇号从 1 起。
     *
     * **语义只有一条**：同色 = 药味重合度高的一群方，方便看图。它**不代表证型、功效或任何
     * 医学分类**（设计红线五），前端图例只能写"组成相近"。
     *
     * 为什么要"阈值阶梯"而不是固定 0.5：连通分量有传递性（A~B、B~C ⇒ A/B/C 同簇），
     * 245 首方按 0.5 跑出来会串出一个吃掉一大片的巨簇，其余全是单点，颜色等于没有信息。
     * 这里按 {@link #CLUSTER_THRESHOLDS} 从 0.5 逐步升到 0.9，超过 {@link #CLUSTER_MAX_SHARE}
     * 比例的大簇留到下一档继续拆；到 0.9 仍拆不开就整块保留（宁可粗糙也不编造分组）。
     *
     * 可复现性：阈值阶梯固定、组件按下标排序后编号，同一份数据永远得到同一套颜色。
     */
    public static int[] clusters(List<String> ids, Map<String, Set<String>> sets) {
        int n = ids.size();
        int[] label = new int[n];
        if (n == 0) {
            return label;
        }

        double[][] sim = similarityMatrix(ids, sets);
        int maxSize = Math.max(CLUSTER_MIN_MAX_SIZE, (int) Math.ceil(n * CLUSTER_MAX_SHARE));

        List<Integer> pending = new ArrayList<>(n);
        for (int i = 0; i < n; i++) {
            pending.add(i);
        }

        int nextLabel = 1;
        for (int step = 0; step < CLUSTER_THRESHOLDS.length && !pending.isEmpty(); step++) {
            double threshold = CLUSTER_THRESHOLDS[step];
            boolean lastStep = step == CLUSTER_THRESHOLDS.length - 1;

            List<List<Integer>> comps = components(pending, sim, threshold);
            // 组件按最小下标排序后再编号，保证簇号与遍历顺序无关
            comps.sort(Comparator.comparingInt(c -> c.get(0)));

            List<Integer> deferred = new ArrayList<>();
            for (List<Integer> comp : comps) {
                if (!lastStep && comp.size() > maxSize) {
                    deferred.addAll(comp);
                } else {
                    for (int idx : comp) {
                        label[idx] = nextLabel;
                    }
                    nextLabel++;
                }
            }
            pending = deferred;
        }
        return label;
    }

    /** 在给定成员集合内，按相似度阈值求连通分量（members 为全局下标，升序）。 */
    private static List<List<Integer>> components(List<Integer> members, double[][] sim, double threshold) {
        int m = members.size();
        int[] parent = new int[m];
        for (int i = 0; i < m; i++) {
            parent[i] = i;
        }
        for (int i = 0; i < m; i++) {
            int gi = members.get(i);
            for (int j = i + 1; j < m; j++) {
                if (sim[gi][members.get(j)] >= threshold) {
                    union(parent, i, j);
                }
            }
        }
        Map<Integer, List<Integer>> byRoot = new LinkedHashMap<>();
        for (int i = 0; i < m; i++) {
            byRoot.computeIfAbsent(find(parent, i), r -> new ArrayList<>()).add(members.get(i));
        }
        return new ArrayList<>(byRoot.values());
    }

    private static int find(int[] parent, int x) {
        int p = x;
        while (parent[p] != p) {
            p = parent[p];
        }
        int cur = x;
        while (parent[cur] != cur) {
            int next = parent[cur];
            parent[cur] = p;
            cur = next;
        }
        return p;
    }

    private static void union(int[] parent, int a, int b) {
        int ra = find(parent, a);
        int rb = find(parent, b);
        if (ra != rb) {
            parent[Math.max(ra, rb)] = Math.min(ra, rb);
        }
    }

    // ------------------------------------------------------------------ 数据指纹

    /**
     * 数据指纹：把参与计算的方剂 ID 与其药味集合都掺进去，任一变化都会换 version。
     * 同版本必须可复现同一张图（契约 §15.5）。
     */
    public static String fingerprint(List<String> ids, Map<String, Set<String>> sets) {
        StringBuilder sb = new StringBuilder("composition|v1");
        for (String id : ids) {
            Set<String> herbs = sets.get(id);
            sb.append('|').append(id).append('#');
            if (herbs != null) {
                sb.append(herbs.size()).append(':');
                for (String h : new TreeSet<>(herbs)) {
                    sb.append(h).append(',');
                }
            }
        }
        return md5Hex(sb.toString()).substring(0, 10);
    }

    /** version 字符串 = 口径 + 数据指纹，例如 {@code composition:v1:3f9a1c2b04}。 */
    public static String version(List<String> ids, Map<String, Set<String>> sets) {
        return METRIC_COMPOSITION + ":v1:" + fingerprint(ids, sets);
    }

    /**
     * 组装点集（地图接口用）。
     *
     * @param ids    已按 id 升序排好的方剂 ID
     * @param names  id → 方名
     * @param sets   id → 药味集合
     */
    public static List<GraphMap.Point> points(List<String> ids, Map<String, String> names,
                                              Map<String, Set<String>> sets) {
        double[][] xy = layout(ids, sets);
        int[] cluster = clusters(ids, sets);
        List<GraphMap.Point> out = new ArrayList<>(ids.size());
        for (int i = 0; i < ids.size(); i++) {
            String id = ids.get(i);
            out.add(new GraphMap.Point(id, "Formula", names.getOrDefault(id, id),
                    xy[i][0], xy[i][1], "c" + cluster[i]));
        }
        return out;
    }

    // ------------------------------------------------------------------ 小工具

    public static double round(double v, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(v * factor) / factor;
    }

    private static String md5Hex(String text) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] digest = md.digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("MD5 不可用", e);
        }
    }
}
