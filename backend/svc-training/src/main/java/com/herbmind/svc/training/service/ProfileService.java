package com.herbmind.svc.training.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Service;

import com.herbmind.contract.training.MeDashboardVO;
import com.herbmind.contract.training.MeProfileVO;
import com.herbmind.svc.training.mapper.PracticeStatMapper;

/**
 * 学习档案（GET /api/biz/me/profile）。
 *
 * 三经典掌握度的真实口径：
 * - 分母 total   = 该书**挂了方剂**的目录节点数（没挂方剂的节点点进去没题，不该算进分母）
 * - 分子 practiced = 用户练过的节点数（training_record.unit_ref 命中节点）
 * - 掌握度 mastery = 该书答题均分；**没有分数就是 0，不用估算值填充**
 *
 * 所以 unit_ref 必须存 book_node.id —— 存证候名的话这条链路全断，只能编数据。
 */
@Service
public class ProfileService {

    /** 掌握度达到多少算「已掌握」 */
    private static final int MASTERED_THRESHOLD = 80;

    private final PracticeStatMapper mapper;
    private final DashboardService dashboardService;

    public ProfileService(PracticeStatMapper mapper, DashboardService dashboardService) {
        this.mapper = mapper;
        this.dashboardService = dashboardService;
    }

    public MeProfileVO profile(String userId) {
        MeDashboardVO dash = dashboardService.dashboard(userId);

        List<Map<String, Object>> nodes = mapper.practiceNodes();
        Set<String> practiced = new HashSet<>(mapper.practicedNodeIds(userId));
        Map<String, Map<String, Object>> scoreByBook = indexByBook(mapper.practicedByBook(userId));

        MeProfileVO vo = new MeProfileVO();
        vo.setRadar(dash.getRadar());
        vo.setClassics(buildClassics(nodes, practiced, scoreByBook));
        vo.setPath(buildPath(userId, nodes, scoreByBook.keySet()));
        vo.setWeakPoints(buildWeakPoints(userId));
        vo.setSummary(buildSummary(dash));
        return vo;
    }

    private Map<String, Map<String, Object>> indexByBook(List<Map<String, Object>> rows) {
        Map<String, Map<String, Object>> map = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            String bookId = str(r.get("bookId"));
            if (bookId != null) {
                map.put(bookId, r);
            }
        }
        return map;
    }

    /**
     * 按书拆解。书的顺序沿用 practiceNodes 的返回顺序（book_id 升序 = 伤寒论 / 温病学 / 金匮要略）。
     */
    private List<MeProfileVO.ClassicItem> buildClassics(List<Map<String, Object>> nodes,
                                                        Set<String> practiced,
                                                        Map<String, Map<String, Object>> scoreByBook) {
        Map<String, String> titles = new LinkedHashMap<>();
        Map<String, Integer> totals = new HashMap<>();
        Map<String, Integer> practicedCount = new HashMap<>();

        for (Map<String, Object> n : nodes) {
            String bookId = str(n.get("bookId"));
            if (bookId == null) {
                continue;
            }
            titles.putIfAbsent(bookId, str(n.get("bookTitle")));
            totals.merge(bookId, 1, Integer::sum);
            if (practiced.contains(str(n.get("nodeId")))) {
                practicedCount.merge(bookId, 1, Integer::sum);
            }
        }

        List<MeProfileVO.ClassicItem> list = new ArrayList<>(titles.size());
        for (Map.Entry<String, String> e : titles.entrySet()) {
            String bookId = e.getKey();
            int total = totals.getOrDefault(bookId, 0);
            int done = practicedCount.getOrDefault(bookId, 0);

            Map<String, Object> scoreRow = scoreByBook.get(bookId);
            Integer avg = scoreRow == null ? null : intOrNull(scoreRow.get("avgScore"));
            int answers = scoreRow == null ? 0 : intOf(scoreRow.get("answers"));

            int mastery = avg == null ? 0 : clamp(avg);
            String status;
            if (done == 0 && answers == 0) {
                status = "未开始";
            } else if (avg != null && mastery >= MASTERED_THRESHOLD) {
                status = "已掌握";
            } else {
                status = "进行中";
            }
            list.add(new MeProfileVO.ClassicItem(bookId, e.getValue(), mastery, done, total, answers, status));
        }
        return list;
    }

    /**
     * 推荐路径：同书续练优先，其次方证多的节点。
     * 理由文案由真实数据拼出（同书已练 / 新经典），不是写死的套话。
     */
    private List<MeProfileVO.PathItem> buildPath(String userId, List<Map<String, Object>> nodes,
                                                 Set<String> touchedBooks) {
        // 书名 → book_id 的映射只建一次，避免在循环里反复查库
        Map<String, String> titleToId = new HashMap<>();
        for (Map<String, Object> n : nodes) {
            String t = str(n.get("bookTitle"));
            if (t != null) {
                titleToId.putIfAbsent(t, str(n.get("bookId")));
            }
        }

        List<Map<String, Object>> rows = mapper.pathCandidates(userId, 3);
        List<MeProfileVO.PathItem> list = new ArrayList<>(rows.size());
        int step = 1;
        for (Map<String, Object> r : rows) {
            String bookTitle = str(r.get("bookTitle"));
            int formulaCount = intOf(r.get("formulaCount"));
            String bookId = titleToId.get(bookTitle);

            String reason = (bookId != null && touchedBooks.contains(bookId))
                    ? "《" + bookTitle + "》续练 · " + formulaCount + " 个方证待练"
                    : "新经典 · 《" + bookTitle + "》" + formulaCount + " 个方证";

            list.add(new MeProfileVO.PathItem(
                    step++,
                    str(r.get("nodeId")),
                    str(r.get("nodeTitle")),
                    bookTitle,
                    formulaCount,
                    reason));
        }
        return list;
    }

    private List<String> buildWeakPoints(String userId) {
        List<Map<String, Object>> rows = mapper.weakWords(userId, 6);
        List<String> list = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            String w = str(r.get("word"));
            if (w != null && !w.isBlank()) {
                list.add(w);
            }
        }
        return list;
    }

    private MeProfileVO.Summary buildSummary(MeDashboardVO dash) {
        MeDashboardVO.Stats s = dash.getStats();
        if (s == null) {
            return new MeProfileVO.Summary(0, 0, 0, 0, 0);
        }
        return new MeProfileVO.Summary(
                nz(s.getAnswerCount()), nz(s.getLitNodes()), nz(s.getStreakDays()),
                nz(s.getTotalMinutes()), nz(s.getMastery()));
    }

    private static int nz(Integer v) {
        return v == null ? 0 : v;
    }

    private static int clamp(int v) {
        return Math.max(0, Math.min(100, v));
    }

    private static Integer intOrNull(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(v.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static int intOf(Object v) {
        Integer i = intOrNull(v);
        return i == null ? 0 : i;
    }

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }
}
