package com.herbmind.svc.training.service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 确定性评分（不调大模型）。
 *
 * 依据设计红线四：「组成比对、集合差集、Jaccard、频次统计一律确定性代码，
 * LLM 只做语言组织与语义理解」。
 *
 * 各分项的可信度差别很大，必须如实区分：
 * - 方剂分：用户药味集合 vs 标准药味集合的 F1 —— **可靠**，就是集合运算；
 * - 辨证分 / 治法分：用户文本的二字词在参考文本里的覆盖率 —— **只是字面重合度**，
 *   不懂近义词（「恶风」与「怕风」不算命中）。Agent 接入后应替换掉这两项。
 */
final class RuleScorer {

    private RuleScorer() {
    }

    /** 总分权重：方剂最能客观比对，给最高权重。 */
    private static final double W_SYNDROME = 0.3;
    private static final double W_FORMULA = 0.4;
    private static final double W_TREATMENT = 0.3;

    /**
     * 药味比对结果。
     */
    record HerbDiff(List<String> hit, List<String> miss, List<String> extra, int score) {
    }

    /**
     * 药味集合比对。score 用 F1：2PR/(P+R)，漏药与多药都扣分。
     * 标准为空时返回 0 分（没有标准答案就不该给分）。
     */
    static HerbDiff compareHerbs(List<String> standard, List<String> userInput) {
        Set<String> std = new LinkedHashSet<>(clean(standard));
        Set<String> usr = new LinkedHashSet<>(clean(userInput));

        if (std.isEmpty()) {
            return new HerbDiff(List.of(), List.of(), new ArrayList<>(usr), 0);
        }

        List<String> hit = new ArrayList<>();
        List<String> miss = new ArrayList<>();
        List<String> extra = new ArrayList<>();

        for (String s : std) {
            if (usr.contains(s)) {
                hit.add(s);
            } else {
                miss.add(s);
            }
        }
        for (String u : usr) {
            if (!std.contains(u)) {
                extra.add(u);
            }
        }

        int score;
        if (usr.isEmpty()) {
            score = 0;
        } else {
            double p = (double) hit.size() / usr.size();
            double r = (double) hit.size() / std.size();
            score = (p + r) == 0 ? 0 : (int) Math.round(200 * p * r / (p + r));
        }
        return new HerbDiff(hit, miss, extra, clamp(score));
    }

    /**
     * 字面覆盖率：把用户文本切成二字词，看有多少能在参考文本里找到。
     *
     * 例：用户「太阳伤寒表实证」→ 太阳/阳伤/伤寒/寒表/表实/实证，
     * 参考文本含「太阳伤寒类方证」→ 命中 4 个 → 约 67 分。
     *
     * 用户没写 → 0 分（不送分）。参考文本为空 → 0 分。
     */
    static int coverage(String userText, String referenceText) {
        Set<String> grams = bigrams(userText);
        if (grams.isEmpty()) {
            return 0;
        }
        String ref = normalize(referenceText);
        if (ref.isEmpty()) {
            return 0;
        }
        int hit = 0;
        for (String g : grams) {
            if (ref.contains(g)) {
                hit++;
            }
        }
        return clamp((int) Math.round(100.0 * hit / grams.size()));
    }

    /** 加权总分。 */
    static int total(int syndrome, int formula, int treatment) {
        return clamp((int) Math.round(
                syndrome * W_SYNDROME + formula * W_FORMULA + treatment * W_TREATMENT));
    }

    /** 二字词集合（去重，保序）。 */
    static Set<String> bigrams(String text) {
        String s = normalize(text);
        Set<String> set = new LinkedHashSet<>();
        for (int i = 0; i + 2 <= s.length(); i++) {
            set.add(s.substring(i, i + 2));
        }
        return set;
    }

    /** 只保留汉字、字母、数字，其余（标点空格）全部去掉。 */
    static String normalize(String text) {
        if (text == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (Character.isLetterOrDigit(c)) {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private static List<String> clean(List<String> raw) {
        List<String> out = new ArrayList<>();
        if (raw == null) {
            return out;
        }
        for (String s : raw) {
            if (s == null) {
                continue;
            }
            String t = s.trim();
            if (!t.isEmpty()) {
                out.add(t);
            }
        }
        return out;
    }

    private static int clamp(int v) {
        return Math.max(0, Math.min(100, v));
    }
}
