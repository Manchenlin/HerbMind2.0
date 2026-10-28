package com.herbmind.svc.training.service;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.herbmind.contract.training.ReciteResultVO;
import com.herbmind.contract.training.ReciteSubmitReq;
import com.herbmind.contract.training.ReciteVO;
import com.herbmind.svc.training.mapper.ExtraPracticeMapper;

/**
 * 背诵打卡（条文默写 + 间隔重复）。
 *
 * ★ 评分是**确定性字面比对**，不是理解语义：
 *   1) 两边都去掉空白与标点；
 *   2) 完全一致 → 100 分；
 *   3) 否则算二元组（bigram）的重合度（Dice 系数）。
 *   为什么不用编辑距离：中文少一个字会让编辑距离很"轻"，
 *   但在条文里少一个「不」字意思正好相反，所以按片段的召回看更贴近实际。
 *
 * ★ 同样的输入必须得到同样的分数与同样的下次复习时间 ——
 *   这是验收标准「同一答案两次跑分一致」的要求，所以间隔天数只由分数决定，
 *   不带任何随机（不加 ±抖动）。
 */
@Service
public class ReciteService {

    private static final int LIMIT = 20;

    private static final DateTimeFormatter MD = DateTimeFormatter.ofPattern("MM-dd");

    private final ExtraPracticeMapper mapper;
    private final String zone;

    public ReciteService(ExtraPracticeMapper mapper,
                         @Value("${herbmind.zone:Asia/Shanghai}") String zone) {
        this.mapper = mapper;
        this.zone = zone;
    }

    // ------------------------------------------------------------------ 列表

    public ReciteVO list(String userId) {
        List<Map<String, Object>> rows = mapper.reciteItems(userId, zone, LIMIT);
        List<ReciteVO.Item> items = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            String reviewDay = str(r.get("reviewDay"));
            String content = firstArticle(str(r.get("content")));
            items.add(new ReciteVO.Item(
                    str(r.get("quoteId")),
                    str(r.get("articleNo")),
                    str(r.get("classicName")),
                    content,
                    str(r.get("plainText")),
                    hintOf(content),
                    normalize(content).length(),
                    Boolean.TRUE.equals(r.get("due")),
                    str(r.get("lastResult")),
                    // 从没背过就没有"下次复习"，显示 null 让前端写「未开始」
                    reviewDay == null ? null : reviewDay));
        }

        Map<String, Object> s = mapper.reciteStats(userId);
        ReciteVO.Stats stats = new ReciteVO.Stats(
                intOf(s, "total"), intOf(s, "due"), intOf(s, "mastered"),
                streakOf(userId));
        return new ReciteVO(items, stats);
    }

    /** 连续打卡天数：复用「有学习行为的日期」口径，和总览页保持一致。 */
    private int streakOf(String userId) {
        List<String> days = mapper.activeDays(userId, zone);
        if (days == null || days.isEmpty()) {
            return 0;
        }
        java.util.Set<LocalDate> set = new java.util.HashSet<>();
        for (String d : days) {
            try {
                set.add(LocalDate.parse(d));
            } catch (RuntimeException ignored) {
                // 脏数据跳过
            }
        }
        LocalDate today = LocalDate.now(ZoneId.of(zone));
        LocalDate cursor = set.contains(today) ? today : today.minusDays(1);
        int n = 0;
        while (set.contains(cursor)) {
            n++;
            cursor = cursor.minusDays(1);
        }
        return n;
    }

    // ------------------------------------------------------------------ 提交

    @Transactional
    public ReciteResultVO submit(String userId, ReciteSubmitReq req) {
        if (req == null || req.quoteId() == null || req.quoteId().isBlank()) {
            throw new IllegalArgumentException("缺少条文 ID，请刷新后重试");
        }
        Map<String, Object> q = mapper.quoteById(req.quoteId());
        if (q == null || q.isEmpty()) {
            throw new IllegalArgumentException("找不到这条条文");
        }
        String standard = firstArticle(str(q.get("content")));
        int score = score(standard, req.text());

        String level = score >= 90 ? "对" : score >= 70 ? "基本对" : "不对";
        int days = score >= 90 ? 7 : score >= 70 ? 3 : 1;

        Map<String, Object> prev = mapper.reciteRecord(userId, req.quoteId());
        double ease = easeAfter(prev == null ? null : prev.get("ease"), score);

        OffsetDateTime next = LocalDate.now(ZoneId.of(zone)).plusDays(days)
                .atTime(4, 0).atZone(ZoneId.of(zone)).toOffsetDateTime();
        mapper.upsertRecite(userId, req.quoteId(), ease, next.toString(), level);
        mapper.insertEvent(userId, "recite", articleLabel(q));

        List<String> matched = new ArrayList<>();
        List<String> missed = new ArrayList<>();
        compare(standard, req.text(), matched, missed);

        return new ReciteResultVO(
                score,
                level,
                matched,
                missed,
                standard,
                days == 1 ? "明天" : days + " 天后",
                "对".equals(level),
                "rule");
    }

    private String articleLabel(Map<String, Object> q) {
        String no = str(q.get("articleNo"));
        String name = str(q.get("classicName"));
        if (name == null) {
            name = "条文";
        }
        return no == null || no.isBlank() ? name : name + " " + no;
    }

    /** 熟练度系数：对了加一点，错了扣一点，夹在 [1.3, 2.8]。目前只做记录，供以后调间隔。 */
    private static double easeAfter(Object prevEase, int score) {
        double ease = 2.5;
        if (prevEase instanceof Number n) {
            ease = n.doubleValue();
        }
        if (score >= 90) {
            ease += 0.1;
        } else if (score < 70) {
            ease -= 0.2;
        }
        return Math.max(1.3, Math.min(2.8, Math.round(ease * 100) / 100.0));
    }

    // ------------------------------------------------------------------ 判分

    /** 0-100。完全一致给满分；否则按二元组重合度。 */
    static int score(String standard, String answer) {
        String a = normalize(standard);
        String b = normalize(answer);
        if (a.isEmpty()) {
            return 0;
        }
        if (b.isEmpty()) {
            return 0;
        }
        if (a.equals(b)) {
            return 100;
        }
        Map<String, Integer> bagA = bigrams(a);
        Map<String, Integer> bagB = bigrams(b);
        int overlap = 0;
        for (Map.Entry<String, Integer> e : bagB.entrySet()) {
            Integer inA = bagA.get(e.getKey());
            if (inA != null) {
                overlap += Math.min(inA, e.getValue());
            }
        }
        int total = Math.max(1, count(bagA) + count(bagB));
        // Dice：2|A∩B| / (|A|+|B|)
        return Math.max(0, Math.min(99, (int) Math.round(200.0 * overlap / total)));
    }

    /** 分句级对照：原文里哪些分句在默写中出现了，哪些漏了。 */
    static void compare(String standard, String answer, List<String> matched, List<String> missed) {
        if (standard == null) {
            return;
        }
        String userText = normalize(answer);
        for (String seg : standard.split("[。；;！!？?，,、\\s]+")) {
            String s = seg.trim().replaceAll("^\\(?\\d+[.、)）]\\s*", "");
            if (s.length() < 4) {
                continue;
            }
            if (userText.contains(normalize(s))) {
                matched.add(s);
            } else {
                missed.add(s);
            }
        }
    }

    /**
     * 起句提示：去掉「1.」这种编号后取前 6 个字。
     *
     * 为什么要给提示：classic_quote.article_no 在这批数据里大量为空，
     * 只显示「伤寒论」三个字、下面一个空输入框，用户根本不知道要默哪条 —— 这不是练习，是猜谜。
     * 给六个字既定了位，又留了绝大部分要背的内容。
     */
    static String hintOf(String content) {
        if (content == null) {
            return "";
        }
        String t = content.replaceAll("^\\s*\\d+[.、]\\s*", "").trim();
        String plain = t;
        if (plain.length() <= 6) {
            return plain;
        }
        return plain.substring(0, 6) + "…";
    }

    /**
     * 只取第一条。
     *
     * 数据里的 classic_quote.content 往往是「1.…(1) 2.…(3) 3.…」的合集，
     * 整段几百字拿去默写没人背得下来。这里按「数字+点」切段取第一段，
     * 规则确定（同一段文本永远切出同一段），不引入任何模型判断。
     */
    static String firstArticle(String content) {
        if (content == null) {
            return null;
        }
        String t = content.trim();
        for (String part : t.split("(?=\\d+[.、])")) {
            String s = part.trim();
            if (s.length() >= 8) {
                return s.length() <= 180 ? s : s.substring(0, 180) + "…";
            }
        }
        return t.length() <= 180 ? t : t.substring(0, 180) + "…";
    }

    /** 去掉所有空白与标点，只留汉字/字母/数字 —— 标点不该影响"背没背下来"。 */
    static String normalize(String s) {
        if (s == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isLetterOrDigit(c)) {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private static Map<String, Integer> bigrams(String s) {
        Map<String, Integer> bag = new HashMap<>();
        for (int i = 0; i + 1 < s.length(); i++) {
            bag.merge(s.substring(i, i + 2), 1, Integer::sum);
        }
        // 单字文本没有二元组，退化成单字
        if (s.length() == 1) {
            bag.put(s, 1);
        }
        return bag;
    }

    private static int count(Map<String, Integer> bag) {
        int n = 0;
        for (int v : bag.values()) {
            n += v;
        }
        return n;
    }

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }

    private static int intOf(Map<String, Object> m, String key) {
        if (m == null || m.get(key) == null) {
            return 0;
        }
        Object v = m.get(key);
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(v.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
