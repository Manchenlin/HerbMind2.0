package com.herbmind.svc.training.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

import com.herbmind.contract.training.BlindboxAnswerVO;
import com.herbmind.contract.training.BlindboxVO;
import com.herbmind.svc.training.mapper.ExtraPracticeMapper;

/**
 * 案例盲盒。
 *
 * 设计取舍：抽盲盒是**只读**操作，不建练习会话。
 * 原因：会话一建，「最近练习」里就会出现一条没有作答的空记录，
 * 统计（平均分、连续打卡）也会被稀释。真正的会话等用户点「我也答一遍」再开。
 *
 * 揭晓答案单独一个接口 —— 这样「先自己辨证」和「看答案」在接口层面就是两件事，
 * 前端不可能因为图省事在抽题时就把答案一起拿到。
 */
@Service
public class BlindboxService {

    private final ExtraPracticeMapper mapper;

    public BlindboxService(ExtraPracticeMapper mapper) {
        this.mapper = mapper;
    }

    public BlindboxVO draw(String userId) {
        Map<String, Object> c = mapper.randomCase();
        if (c == null || c.isEmpty()) {
            throw new IllegalArgumentException("暂时没有可揭晓的医案（需要案例挂上方剂且有完整原文）");
        }
        Map<String, Object> stat = mapper.blindboxStats(userId);

        return new BlindboxVO(
                str(c.get("caseId")),
                str(c.get("title")),
                trim(str(c.get("illness")), 420),
                str(c.get("exam")),
                str(c.get("nodeId")),
                str(c.get("nodeTitle")),
                str(c.get("bookTitle")),
                str(c.get("formulaId")),
                intOf(stat, "drawn"),
                stat == null ? null : intOrNull(stat.get("avgScore")));
    }

    public BlindboxAnswerVO reveal(String caseId) {
        if (caseId == null || caseId.isBlank()) {
            throw new IllegalArgumentException("缺少案例 ID");
        }
        Map<String, Object> a = mapper.caseAnswer(caseId);
        if (a == null || a.isEmpty()) {
            throw new IllegalArgumentException("找不到这个医案的原文，换一个盲盒试试");
        }

        String formulaName = str(a.get("formulaName"));

        List<String> parts = new ArrayList<>(3);
        if (formulaName != null && !formulaName.isBlank()) {
            parts.add("参考方：" + formulaName);
        }
        String efficacy = str(a.get("efficacy"));
        if (efficacy != null && !efficacy.isBlank()) {
            parts.add("治法：" + stripTail(trim(efficacy, 90)));
        }
        String syn = str(a.get("syndromeText"));
        if (syn != null && !syn.isBlank()) {
            parts.add("辨证：" + stripTail(trim(syn, 120)));
        }
        // 用「。」连接而不是自己拼标点 —— 原文本身末尾常带句号，不掐掉就会拼出「。。」
        String refText = parts.isEmpty() ? "本条的原文对照暂缺。" : String.join("。", parts) + "。";
        return new BlindboxAnswerVO(formulaName, syn, efficacy, List.of(), refText);
    }

    /** 带处方的版本：formulaId 由前端从抽签结果里带回来，这样才能取到药味明细。 */
    public BlindboxAnswerVO reveal(String caseId, String formulaId) {
        BlindboxAnswerVO base = reveal(caseId);
        if (formulaId == null || formulaId.isBlank()) {
            return base;
        }
        List<Map<String, Object>> rows = mapper.caseHerbs(formulaId);
        List<String> prescription = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            String herb = str(r.get("herb"));
            if (herb == null || herb.isBlank()) {
                continue;
            }
            StringBuilder one = new StringBuilder(herb);
            Object dose = r.get("dose");
            if (dose != null) {
                one.append(' ').append(fmtDose(dose));
            }
            String unit = str(r.get("unit"));
            if (unit != null && !unit.isBlank()) {
                one.append(unit);
            }
            prescription.add(one.toString());
        }

        String refText = base.refText();
        if (!prescription.isEmpty()) {
            refText = refText + "处方：" + String.join("、", prescription) + "。";
        }
        return new BlindboxAnswerVO(base.formulaName(), base.syndromeText(), base.efficacy(),
                prescription, refText);
    }

    private static String fmtDose(Object dose) {        try {
            double d = Double.parseDouble(dose.toString());
            return d == Math.rint(d) ? String.valueOf((long) d) : String.valueOf(d);
        } catch (NumberFormatException e) {
            return dose.toString();
        }
    }

    private static String trim(String s, int max) {
        if (s == null) {
            return null;
        }
        String t = s.trim().replaceAll("\\s+", " ");
        return t.length() <= max ? t : t.substring(0, max) + "…";
    }

    /** 掐掉末尾的句号/分号，避免和拼接用的「。」叠成「。。」 */
    private static String stripTail(String s) {
        if (s == null) {
            return "";
        }
        return s.replaceAll("[。；;.\\s]+$", "");
    }

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }

    private static int intOf(Map<String, Object> m, String key) {
        Integer v = m == null ? null : intOrNull(m.get(key));
        return v == null ? 0 : v;
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
