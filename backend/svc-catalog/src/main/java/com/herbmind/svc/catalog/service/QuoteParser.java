package com.herbmind.svc.catalog.service;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.stereotype.Component;

import com.herbmind.contract.catalog.QuoteItemVO;

/**
 * 条文解析器。
 *
 * 真实数据里 classic_quote.content 是**一整段**，内部按
 * 「1.太阳之为病……(1) 2.太阳病……(3)」 的格式罗列多条条文（括号里是条文号）。
 * 本类把它拆成逐条，供条文页 / 反向索引 / 检索使用。
 *
 * 兼容：没有编号的纯文本（整段作为一条，no = null）。
 */
@Component
public class QuoteParser {

    private static final Pattern ITEM = Pattern.compile(
            "(\\d{1,4})\\s*[.．、]\\s*(.+?)\\s*[(（](\\d{1,4})[)）]",
            Pattern.DOTALL);

    /** 拆分条文；返回的 no 为括号中的条文号（如 "35"）。 */
    public List<QuoteItemVO> parse(String content) {
        List<QuoteItemVO> items = new ArrayList<>();
        if (content == null || content.isBlank()) {
            return items;
        }
        Matcher m = ITEM.matcher(content);
        int last = 0;
        while (m.find()) {
            String text = clean(m.group(2));
            String no = m.group(3);
            if (!text.isEmpty()) {
                items.add(new QuoteItemVO(no, text, label(no), new ArrayList<>(), new ArrayList<>()));
            }
            last = m.end();
        }
        if (items.isEmpty()) {
            String text = clean(content);
            if (!text.isEmpty()) {
                items.add(new QuoteItemVO(null, text, null, new ArrayList<>(), new ArrayList<>()));
            }
        } else if (last < content.length()) {
            // 尾部残留（极少数格式不规整的行）也保留，避免丢内容
            String tail = clean(content.substring(last));
            if (tail.length() > 4) {
                items.add(new QuoteItemVO(null, tail, null, new ArrayList<>(), new ArrayList<>()));
            }
        }
        return items;
    }

    public String label(String no) {
        return no == null ? null : "第 " + no + " 条";
    }

    /** 压平换行、去多余空白（条文卡片按行排版，不保留原始折行）。 */
    public static String clean(String s) {
        if (s == null) {
            return "";
        }
        return s.replaceAll("[\\r\\n]+", " ").replaceAll("\\s{2,}", " ").trim();
    }
}
