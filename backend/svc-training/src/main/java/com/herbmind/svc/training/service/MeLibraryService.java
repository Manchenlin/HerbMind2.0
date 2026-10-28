package com.herbmind.svc.training.service;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.herbmind.contract.training.FormulaLibVO;
import com.herbmind.contract.training.PathVO;
import com.herbmind.contract.training.WrongBookVO;
import com.herbmind.svc.training.mapper.MeLibraryMapper;
import com.herbmind.svc.training.mapper.PracticeStatMapper;

/**
 * 错题本 / 我的方证库 / 学习路径。
 *
 * 三个页面都是「把已有练习数据换个角度摊开」，没有一处需要新采集数据。
 * 凡是页面上的数字，都能在同一条 SQL 里指回原始表。
 */
@Service
public class MeLibraryService {

    private static final DateTimeFormatter MM_DD = DateTimeFormatter.ofPattern("MM-dd");

    /** 移出错题本的门槛：练到 60 分以上才有资格点「已掌握」。 */
    private static final int CLEAR_SCORE = 60;

    private final MeLibraryMapper mapper;
    private final PracticeStatMapper practice;
    private final String zone;

    public MeLibraryService(MeLibraryMapper mapper, PracticeStatMapper practice,
                            @Value("${herbmind.zone:Asia/Shanghai}") String zone) {
        this.mapper = mapper;
        this.practice = practice;
        this.zone = zone;
    }

    // ------------------------------------------------------------------ 错题本

    public WrongBookVO wrongBook(String userId) {
        List<Map<String, Object>> rows = mapper.wrongBook(userId, zone);
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        List<WrongBookVO.Item> items = new ArrayList<>(rows.size());
        int cleared = 0;
        for (Map<String, Object> r : rows) {
            int last = intOf(r.get("lastScore"));
            Integer best = intOrNull(r.get("bestScore"));
            // 「已清」= 后来练及格了，而且确实比进错题本那次高。
            // 只看 best>=60 会把「当初就以 63 分进来」的也算成已清，那是自欺。
            if (best != null && best >= CLEAR_SCORE && best > last) {
                cleared++;
            }
            items.add(new WrongBookVO.Item(
                    str(r.get("unitRef")),
                    nullToEmpty(str(r.get("nodeTitle"))),
                    nullToEmpty(str(r.get("bookTitle"))),
                    last,
                    best,
                    intOf(r.get("attempts")),
                    dayLabel(str(r.get("addedDay")), today)));
        }
        return new WrongBookVO(items, new WrongBookVO.Summary(items.size(), cleared));
    }

    @Transactional
    public WrongBookVO removeWrong(String userId, String unitRef) {
        if (unitRef == null || unitRef.isBlank()) {
            throw new IllegalArgumentException("缺少单元 ID");
        }
        mapper.deleteWrong(userId, unitRef);
        return wrongBook(userId);
    }

    // ---------------------------------------------------------------- 我的方证库

    public FormulaLibVO collection(String userId) {
        List<Map<String, Object>> rows = mapper.collection(userId, zone);
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        List<FormulaLibVO.Item> items = new ArrayList<>(rows.size());
        int mastered = 0;
        int learning = 0;
        int weak = 0;
        for (Map<String, Object> r : rows) {
            int best = intOf(r.get("bestScore"));
            String status = best >= 80 ? "已掌握" : best >= CLEAR_SCORE ? "待巩固" : "需重练";
            switch (status) {
                case "已掌握" -> mastered++;
                case "待巩固" -> learning++;
                default -> weak++;
            }
            items.add(new FormulaLibVO.Item(
                    str(r.get("formulaId")),
                    nullToEmpty(str(r.get("name"))),
                    nullToEmpty(str(r.get("nodeTitle"))),
                    nullToEmpty(str(r.get("bookTitle"))),
                    intOf(r.get("practices")),
                    best,
                    intOf(r.get("lastScore")),
                    dayLabel(str(r.get("lastDay")), today),
                    status));
        }
        return new FormulaLibVO(items, new FormulaLibVO.Summary(items.size(), mastered, learning, weak));
    }

    // ------------------------------------------------------------------ 学习路径

    /**
     * 完整学习路径 = 已练（按时间正序，看得出成长线）+ 待练（同书优先，最多 6 步）。
     *
     * 没练过的用户不会得到空页面：todo 段照样有内容，只是 done 为空 ——
     * 这正是"从头开始练"该看到的样子。
     */
    public PathVO path(String userId) {
        List<Map<String, Object>> doneRows = mapper.practicedSteps(userId);
        LocalDate today = LocalDate.now(ZoneId.of(zone));

        List<PathVO.Step> done = new ArrayList<>(doneRows.size());
        String lastBook = null;
        int seq = 1;
        for (Map<String, Object> r : doneRows) {
            String book = nullToEmpty(str(r.get("bookTitle")));
            lastBook = book;
            done.add(new PathVO.Step(
                    seq++,
                    str(r.get("nodeId")),
                    nullToEmpty(str(r.get("title"))),
                    book,
                    intOf(r.get("formulaCount")),
                    intOrNull(r.get("score")),
                    "已练 · " + dayLabel(str(r.get("lastAt")), today),
                    "done"));
        }

        List<PathVO.Step> todo = new ArrayList<>();
        List<Map<String, Object>> todoRows = practice.pathCandidates(userId, 6);
        for (Map<String, Object> r : todoRows) {
            int step = todo.size() + 1;
            String book = nullToEmpty(str(r.get("bookTitle")));
            String reason = book.equals(lastBook)
                    ? "接着《" + book + "》往下练 · " + intOf(r.get("formulaCount")) + " 个方证"
                    : "换个经典 · 《" + book + "》 · " + intOf(r.get("formulaCount")) + " 个方证";
            todo.add(new PathVO.Step(
                    step,
                    str(r.get("nodeId")),
                    nullToEmpty(str(r.get("nodeTitle"))),
                    book,
                    intOf(r.get("formulaCount")),
                    null,
                    reason,
                    // 第一步是「下一站」，其余是「之后」——前端据此高亮
                    step == 1 ? "doing" : "todo"));
        }

        Integer totalNodes = mapper.practiceableTotal();
        int total = totalNodes == null ? 0 : totalNodes;
        int practiced = done.size();
        int percent = total == 0 ? 0 : Math.min(100, practiced * 100 / total);
        return new PathVO(practiced, total, percent, done, todo);
    }

    // ------------------------------------------------------------------ 工具

    /** 今天 / 昨天 / 10-09 */
    private String dayLabel(String iso, LocalDate today) {
        if (iso == null || iso.length() < 10) {
            return "";
        }
        try {
            LocalDate d = LocalDate.parse(iso.substring(0, 10));
            if (d.equals(today)) {
                return "今天";
            }
            if (d.equals(today.minusDays(1))) {
                return "昨天";
            }
            return d.format(MM_DD);
        } catch (RuntimeException e) {
            return iso;
        }
    }

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    private static int intOf(Object v) {
        Integer i = intOrNull(v);
        return i == null ? 0 : i;
    }

    private static Integer intOrNull(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return (int) Math.round(Double.parseDouble(v.toString()));
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
