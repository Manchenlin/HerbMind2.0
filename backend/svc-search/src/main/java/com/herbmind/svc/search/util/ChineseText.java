package com.herbmind.svc.search.util;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 中文检索的轻量文本工具（不依赖分词器，pg_jieba 未装时也能召回）。
 *
 * 思路：查询串先整体作为一个词项（短查询，如「麻黄汤」），
 * 长句（自然语言，如「无汗而喘、脉浮紧用什么方」）切成 2-gram 词项，
 * 再滤掉疑问/口语停用词。
 */
public final class ChineseText {

    private static final Set<String> STOP = Set.of(
            "什么", "怎么", "如何", "用什", "么方", "请问", "可以", "哪些", "哪个",
            "是否", "一个", "这个", "那个", "以及", "还是", "就是", "因为", "所以",
            "的话", "有没", "没有", "我们", "你们", "他们", "一下", "怎样", "为何");

    private ChineseText() {
    }

    public static List<String> keywords(String q) {
        if (q == null) {
            return List.of();
        }
        String s = q.trim();
        if (s.isEmpty()) {
            return List.of();
        }
        Set<String> out = new LinkedHashSet<>();
        // 短查询整体作为一个词项（如「麻黄汤」「无汗而喘」）；长句只用 2-gram，避免整句永远匹配不上
        if (s.length() <= 8) {
            out.add(s);
        }
        for (String part : s.split("[\\s，。、,.;:!?？；：（）()“”\"'·/]+")) {
            if (part.isBlank()) {
                continue;
            }
            if (part.length() <= 4) {
                out.add(part);
            } else {
                for (int i = 0; i + 1 < part.length(); i++) {
                    out.add(part.substring(i, i + 2));
                }
            }
        }
        out.removeIf(t -> t.length() < 2 || STOP.contains(t));
        return out.stream().limit(8).toList();
    }

    /** 单行摘要，围绕命中词取窗口。 */
    public static String snippet(String text, String q) {
        String t = clean(text);
        if (t.isEmpty()) {
            return "";
        }
        int hit = q == null ? -1 : t.indexOf(q.trim());
        if (hit < 0) {
            for (String k : keywords(q)) {
                hit = t.indexOf(k);
                if (hit >= 0) {
                    break;
                }
            }
        }
        if (hit < 0) {
            return t.length() <= 160 ? t : t.substring(0, 160) + "…";
        }
        int start = Math.max(0, hit - 50);
        int end = Math.min(t.length(), hit + 110);
        return (start > 0 ? "…" : "") + t.substring(start, end) + (end < t.length() ? "…" : "");
    }

    public static String clean(String s) {
        if (s == null) {
            return "";
        }
        return s.replaceAll("[\\r\\n\\t]+", " ").replaceAll("\\s{2,}", " ").trim();
    }
}
