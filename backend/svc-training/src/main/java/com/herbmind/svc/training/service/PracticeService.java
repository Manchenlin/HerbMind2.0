package com.herbmind.svc.training.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herbmind.contract.training.AnswerScoreVO;
import com.herbmind.contract.training.PracticeQuestionVO;
import com.herbmind.contract.training.SubmitAnswerReq;
import com.herbmind.contract.training.TrainOptionsVO;
import com.herbmind.svc.training.mapper.PracticeStatMapper;

/**
 * 练习台 / 出题 / 提交评分。
 *
 * 会话 ID 编码规则：{@code s_<formulaId>_<8位随机>}。
 * 这样「这次会话答的是哪道题」不需要额外存字段（表结构里没有），服务重启后也能解析。
 * 代价是 formulaId 对外可见 —— 但题目本来就来自它，不算泄题（题面里没有方名）。
 *
 * 评分：确定性规则（见 RuleScorer），不调大模型。Agent 语义评分的接入点在 submit()。
 */
@Service
public class PracticeService {

    private static final List<String> MODES = List.of("先思后看", "仅辨证", "仅方剂");
    private static final String DEFAULT_MODE = "先思后看";

    /** 低于这个分数进错题本 */
    private static final int WRONG_BOOK_THRESHOLD = 60;

    private static final DateTimeFormatter HH_MM = DateTimeFormatter.ofPattern("HH:mm");
    private static final DateTimeFormatter MM_DD = DateTimeFormatter.ofPattern("MM-dd");

    private final PracticeStatMapper mapper;
    private final String zone;

    public PracticeService(PracticeStatMapper mapper,
                           @Value("${herbmind.zone:Asia/Shanghai}") String zone) {
        this.mapper = mapper;
        this.zone = zone;
    }

    // ------------------------------------------------------------------ 练习台

    public TrainOptionsVO options(String userId) {
        Set<String> practiced = new HashSet<>(mapper.practicedNodeIds(userId));

        // 按书分组，保持 practiceNodes() 的返回顺序（book_id 升序）
        Map<String, String> bookTitles = new LinkedHashMap<>();
        Map<String, List<TrainOptionsVO.NodeOption>> grouped = new LinkedHashMap<>();
        for (Map<String, Object> n : mapper.practiceNodes()) {
            String bookId = str(n.get("bookId"));
            if (bookId == null) {
                continue;
            }
            bookTitles.putIfAbsent(bookId, str(n.get("bookTitle")));
            grouped.computeIfAbsent(bookId, k -> new ArrayList<>()).add(
                    new TrainOptionsVO.NodeOption(
                            str(n.get("nodeId")),
                            str(n.get("nodeTitle")),
                            intOf(n.get("formulaCount")),
                            practiced.contains(str(n.get("nodeId")))));
        }

        List<TrainOptionsVO.BookOption> books = new ArrayList<>(bookTitles.size());
        for (Map.Entry<String, String> e : bookTitles.entrySet()) {
            books.add(new TrainOptionsVO.BookOption(
                    e.getKey(), e.getValue(), grouped.getOrDefault(e.getKey(), List.of())));
        }

        TrainOptionsVO vo = new TrainOptionsVO();
        vo.setBooks(books);
        vo.setModes(MODES);
        vo.setRecent(buildRecent(userId));
        return vo;
    }

    private List<TrainOptionsVO.RecentItem> buildRecent(String userId) {
        List<Map<String, Object>> rows = mapper.recentSessions(userId, zone, 5);
        LocalDateTime now = LocalDateTime.now(ZoneId.of(zone));
        List<TrainOptionsVO.RecentItem> list = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            list.add(new TrainOptionsVO.RecentItem(
                    str(r.get("sessionId")),
                    str(r.get("nodeTitle")),
                    str(r.get("mode")),
                    friendlyTime(str(r.get("day")), now),
                    intOrNull(r.get("score")),
                    intOf(r.get("durationSeconds")),
                    Boolean.TRUE.equals(r.get("inWrongBook"))));
        }
        return list;
    }

    // ------------------------------------------------------------------ 出题

    @Transactional
    public PracticeQuestionVO start(String userId, String nodeRef, String mode) {
        return start(userId, nodeRef, mode, null);
    }

    /**
     * @param formulaId 指定出哪个方（盲盒「我也答一遍」用）。
     *                  为空则在该单元里随机 —— 正常练习不该每次都是同一题。
     */
    @Transactional
    public PracticeQuestionVO start(String userId, String nodeRef, String mode, String formulaId) {
        if (nodeRef == null || nodeRef.isBlank()) {
            throw new IllegalArgumentException("请先选择练习内容");
        }
        String useMode = MODES.contains(mode) ? mode : DEFAULT_MODE;

        List<Map<String, Object>> questions = mapper.nodeQuestions(nodeRef);
        if (questions.isEmpty()) {
            throw new IllegalArgumentException("该单元暂无可练的方证，换一个单元试试");
        }
        Map<String, Object> q = pick(questions, formulaId);

        String pickedFormulaId = str(q.get("formulaId"));
        String sessionId = newSessionId(pickedFormulaId);
        mapper.insertSession(sessionId, userId, nodeRef, useMode);

        PracticeQuestionVO vo = new PracticeQuestionVO();
        vo.setSessionId(sessionId);
        vo.setIndex(1);
        vo.setTotal(questions.size());
        vo.setNodeId(nodeRef);
        vo.setNodeTitle(str(q.get("nodeTitle")));
        vo.setBookTitle(str(q.get("bookTitle")));
        vo.setCaseId(str(q.get("caseId")));
        vo.setSymptoms(trim(str(q.get("symptoms")), 260));
        vo.setSigns(trim(str(q.get("signs")), 160));
        vo.setHint(buildHint(str(q.get("symptoms"))));
        return vo;
    }

    /** 指定了方就出那道题；指定的方不在本单元里则退回随机（不让盲盒变成"抽到就报错"）。 */
    private static Map<String, Object> pick(List<Map<String, Object>> questions, String formulaId) {
        if (formulaId != null && !formulaId.isBlank()) {
            for (Map<String, Object> q : questions) {
                if (formulaId.equals(str(q.get("formulaId")))) {
                    return q;
                }
            }
        }
        return questions.get(ThreadLocalRandom.current().nextInt(questions.size()));
    }

    /**
     * 审题提示：从症状里挑三个短词，只提示"往哪个方向辨"，不给答案。
     * 原文里就有的词，不是凭空生成的。
     */
    private String buildHint(String symptoms) {
        if (symptoms == null || symptoms.isBlank()) {
            return "先看主症，再辨表里寒热虚实。";
        }
        List<String> picks = new ArrayList<>(3);
        for (String part : symptoms.split("[、，,。；;\\s]+")) {
            String p = part.trim();
            if (p.length() >= 2 && p.length() <= 8) {
                picks.add(p);
            }
            if (picks.size() == 3) {
                break;
            }
        }
        if (picks.isEmpty()) {
            return "先看主症，再辨表里寒热虚实。";
        }
        StringBuilder sb = new StringBuilder("注意");
        for (String p : picks) {
            sb.append("「").append(p).append("」");
        }
        sb.append(" —— 先辨表里寒热虚实。");
        return sb.toString();
    }

    // ------------------------------------------------------------------ 提交评分

    @Transactional
    public AnswerScoreVO submit(String userId, SubmitAnswerReq req) {
        if (req == null || req.getSessionId() == null || req.getSessionId().isBlank()) {
            throw new IllegalArgumentException("缺少会话 ID，请重新开始练习");
        }
        Map<String, Object> session = mapper.sessionInfo(req.getSessionId(), userId);
        if (session == null || session.isEmpty()) {
            throw new IllegalArgumentException("会话不存在或已失效，请重新开始练习");
        }
        String nodeId = str(session.get("nodeId"));
        String formulaId = formulaIdOf(req.getSessionId());

        Map<String, Object> std = formulaId == null ? null : mapper.formulaDetail(formulaId);
        if (std == null || std.isEmpty()) {
            throw new IllegalArgumentException("找不到本题的标准答案，请重新开始练习");
        }

        // ---- 确定性评分 ----
        List<String> stdHerbs = new ArrayList<>();
        for (Map<String, Object> h : mapper.formulaHerbs(formulaId)) {
            String name = str(h.get("herb"));
            if (name != null && !name.isBlank()) {
                stdHerbs.add(name);
            }
        }
        List<String> userHerbs = new ArrayList<>();
        if (req.getPrescription() != null) {
            for (SubmitAnswerReq.HerbItem it : req.getPrescription()) {
                if (it != null && it.getHerb() != null && !it.getHerb().isBlank()) {
                    userHerbs.add(it.getHerb().trim());
                }
            }
        }

        RuleScorer.HerbDiff diff = RuleScorer.compareHerbs(stdHerbs, userHerbs);

        String formulaName = str(std.get("formulaName"));
        String nodeTitle = str(std.get("nodeTitle"));
        String symptoms = str(std.get("symptoms"));
        String efficacy = str(std.get("efficacy"));

        // 辨证的参考文本 = 目录节点标题 + 方名 + 症状描述
        String syndromeRef = join(nodeTitle, formulaName, symptoms);
        int syndromeScore = RuleScorer.coverage(req.getSyndrome(), syndromeRef);
        int treatmentScore = RuleScorer.coverage(req.getTreatment(), efficacy);
        int total = RuleScorer.total(syndromeScore, diff.score(), treatmentScore);

        // ---- 落库 ----
        String answerId = "a_" + shortId();
        mapper.insertAnswer(answerId, req.getSessionId(),
                nullToEmpty(req.getSyndrome()), nullToEmpty(req.getTreatment()),
                toJson(req.getPrescription()));
        mapper.insertScore("sc_" + shortId(), answerId,
                syndromeScore, diff.score(), treatmentScore, total,
                toJson(diff.hit()), toJson(diff.miss()), toJson(diff.extra()));

        // 先结算时长，再写记录（记录里的时长要取会话表的值）
        mapper.updateDuration(req.getSessionId(), userId, elapsedMs(session));
        mapper.insertRecord(userId, req.getSessionId(), nodeId,
                nullToEmpty(req.getSyndrome()), total >= WRONG_BOOK_THRESHOLD);
        if (total < WRONG_BOOK_THRESHOLD && nodeId != null) {
            mapper.upsertWrongBook(userId, nodeId, total);
        }

        AnswerScoreVO vo = new AnswerScoreVO();
        vo.setAnswerId(answerId);
        vo.setTotal(total);
        vo.setSyndromeScore(syndromeScore);
        vo.setFormulaScore(diff.score());
        vo.setTreatmentScore(treatmentScore);
        vo.setHit(diff.hit());
        vo.setMiss(diff.miss());
        vo.setExtra(diff.extra());
        vo.setRefText(buildRefText(formulaName, nodeTitle, efficacy, stdHerbs, formulaId));
        vo.setScoredBy("rule");
        return vo;
    }

    /**
     * 原著对照。提交后才给 —— 这是「先思后看」的"看"。
     */
    private String buildRefText(String formulaName, String nodeTitle, String efficacy,
                                List<String> herbs, String formulaId) {
        StringBuilder sb = new StringBuilder();
        if (formulaName != null) {
            sb.append("参考方：").append(formulaName);
        }
        if (nodeTitle != null) {
            sb.append("（").append(nodeTitle).append("）");
        }
        if (efficacy != null && !efficacy.isBlank()) {
            sb.append("。治法：").append(trim(efficacy, 80));
        }

        List<Map<String, Object>> rows = mapper.formulaHerbs(formulaId);
        if (!rows.isEmpty()) {
            sb.append("。组成：");
            boolean first = true;
            for (Map<String, Object> r : rows) {
                if (!first) {
                    sb.append("、");
                }
                sb.append(str(r.get("herb")));
                Object dose = r.get("dose");
                if (dose != null) {
                    sb.append(" ").append(fmtDose(dose));
                }
                String unit = str(r.get("unit"));
                if (unit != null && !unit.isBlank()) {
                    sb.append(unit);
                }
                first = false;
            }
        }
        return sb.append("。").toString();
    }

    private static String fmtDose(Object dose) {
        try {
            double d = Double.parseDouble(dose.toString());
            return d == Math.rint(d) ? String.valueOf((long) d) : String.valueOf(d);
        } catch (NumberFormatException e) {
            return dose.toString();
        }
    }

    /** 会话耗时：从 started_at 到现在。会话表里没有记录开始时间以外的信息，只能这样算。 */
    private long elapsedMs(Map<String, Object> session) {
        Object sec = session.get("elapsedSeconds");
        if (sec instanceof Number n) {
            return Math.max(0, n.longValue() * 1000);
        }
        return 0;
    }

    // ------------------------------------------------------------------ 工具

    private static String newSessionId(String formulaId) {
        return "s_" + (formulaId == null ? "x" : formulaId) + "_" + shortId();
    }

    /**
     * 从会话 ID 里取回题目 ID。
     *
     * 格式是 {@code s_<formulaId>_<8位随机>}，而 formulaId 自己就带下划线（f_170），
     * 所以**不能按 '_' 分割取第 2 段**（那样只会拿到 "f"）。正确做法是掐头去尾：
     * 去掉 "s_" 前缀和最后一个 "_<随机>" 后缀。
     */
    private static String formulaIdOf(String sessionId) {
        if (sessionId == null || !sessionId.startsWith("s_") || sessionId.length() <= 2) {
            return null;
        }
        String body = sessionId.substring(2);
        int idx = body.lastIndexOf('_');
        return idx > 0 ? body.substring(0, idx) : body;
    }

    private static String shortId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 8);
    }

    private static String toJson(Object o) {
        try {
            return o == null ? "[]" : JSON.writeValueAsString(o);
        } catch (JsonProcessingException e) {
            return "[]";
        }
    }

    /** 复用同一个 ObjectMapper（线程安全，可共享）。 */
    private static final ObjectMapper JSON = new ObjectMapper();

    private static String join(String... parts) {
        StringBuilder sb = new StringBuilder();
        for (String p : parts) {
            if (p != null && !p.isBlank()) {
                sb.append(p).append(' ');
            }
        }
        return sb.toString();
    }

    private static String trim(String s, int max) {
        if (s == null) {
            return null;
        }
        String t = s.trim();
        return t.length() <= max ? t : t.substring(0, max) + "…";
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    /** yyyy-MM-dd HH:mm → 今天 20:14 / 昨天 19:50 / 10-09 */
    private String friendlyTime(String raw, LocalDateTime now) {
        if (raw == null || raw.length() < 16) {
            return "";
        }
        try {
            LocalDateTime t = LocalDateTime.parse(raw.replace(' ', 'T'));
            LocalDate d = t.toLocalDate();
            String hm = t.format(HH_MM);
            if (d.equals(now.toLocalDate())) {
                return "今天 " + hm;
            }
            if (d.equals(now.toLocalDate().minusDays(1))) {
                return "昨天 " + hm;
            }
            return t.format(MM_DD);
        } catch (RuntimeException e) {
            return raw;
        }
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
