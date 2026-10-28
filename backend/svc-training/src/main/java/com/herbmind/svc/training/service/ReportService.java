package com.herbmind.svc.training.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herbmind.contract.training.MeDashboardVO;
import com.herbmind.contract.training.MeReportVO;
import com.herbmind.svc.training.mapper.MeLibraryMapper;

/**
 * 评分报告（/train/report/:answerId）。
 *
 * 只做"把库里这次作答摊开"这一件事，不重新评分 ——
 * 报告必须和提交时看到的分一致，重算一遍只会在换了评分策略后产生两份不同的分数。
 *
 * ★ 关于雷达：单题只有三个分项，凑不出五维。
 *   所以这里给的是**累计能力画像**（与「我的·总览」同一口径），界面上写清「累计」。
 */
@Service
public class ReportService {

    private static final DateTimeFormatter HH_MM = DateTimeFormatter.ofPattern("HH:mm");
    private static final DateTimeFormatter MM_DD_HM = DateTimeFormatter.ofPattern("MM-dd HH:mm");

    private final MeLibraryMapper mapper;
    private final DashboardService dashboard;
    private final String zone;
    private final ObjectMapper json = new ObjectMapper();

    public ReportService(MeLibraryMapper mapper, DashboardService dashboard,
                         @Value("${herbmind.zone:Asia/Shanghai}") String zone) {
        this.mapper = mapper;
        this.dashboard = dashboard;
        this.zone = zone;
    }

    public MeReportVO report(String userId, String answerId) {
        if (answerId == null || answerId.isBlank()) {
            throw new IllegalArgumentException("缺少答题记录 ID");
        }
        Map<String, Object> r = mapper.report(userId, answerId, zone);
        if (r == null || r.isEmpty()) {
            throw new IllegalArgumentException("找不到这条答题记录（可能不属于当前账号）");
        }

        String formulaId = str(r.get("formulaId"));
        List<String> prescription = new ArrayList<>();
        if (formulaId != null) {
            for (Map<String, Object> h : mapper.herbs(formulaId)) {
                String herb = str(h.get("herb"));
                if (herb == null || herb.isBlank()) {
                    continue;
                }
                StringBuilder one = new StringBuilder(herb);
                Object dose = h.get("dose");
                if (dose != null) {
                    one.append(' ').append(fmtDose(dose));
                }
                String unit = str(h.get("unit"));
                if (unit != null && !unit.isBlank()) {
                    one.append(unit);
                }
                prescription.add(one.toString());
            }
        }

        return new MeReportVO(
                str(r.get("answerId")),
                str(r.get("sessionId")),
                nullToEmpty(str(r.get("nodeTitle"))),
                nullToEmpty(str(r.get("bookTitle"))),
                nullToEmpty(str(r.get("formulaName"))),
                str(r.get("caseId")),
                friendlyTime(str(r.get("submittedAt"))),
                intOf(r.get("durationSeconds")),
                intOf(r.get("total")),
                intOf(r.get("syndromeScore")),
                intOf(r.get("formulaScore")),
                intOf(r.get("treatmentScore")),
                jsonList(r.get("hit")),
                jsonList(r.get("miss")),
                jsonList(r.get("extra")),
                buildRefText(r, prescription),
                nullToEmpty(str(r.get("userSyndrome"))),
                nullToEmpty(str(r.get("userTreatment"))),
                prescription,
                // 报告目前由确定性规则产出；接 Agent 语义评分后这里会变成 agent
                "rule",
                radarOf(userId));
    }

    private List<MeReportVO.Radar> radarOf(String userId) {
        List<MeDashboardVO.RadarItem> items = dashboard.dashboard(userId).getRadar();
        List<MeReportVO.Radar> list = new ArrayList<>();
        if (items != null) {
            for (MeDashboardVO.RadarItem i : items) {
                list.add(new MeReportVO.Radar(i.getKey(), i.getLabel(), i.getValue()));
            }
        }
        return list;
    }

    private String buildRefText(Map<String, Object> r, List<String> prescription) {
        StringBuilder sb = new StringBuilder();
        String name = str(r.get("formulaName"));
        if (name != null && !name.isBlank()) {
            sb.append("参考方：").append(name);
        }
        String eff = str(r.get("efficacy"));
        if (eff != null && !eff.isBlank()) {
            sb.append("。治法：").append(stripTail(trim(eff, 90)));
        }
        String syn = str(r.get("stdSyndrome"));
        if (syn != null && !syn.isBlank()) {
            sb.append("。辨证：").append(stripTail(trim(syn, 120)));
        }
        if (!prescription.isEmpty()) {
            sb.append("。组成：").append(String.join("、", prescription));
        }
        String out = sb.toString();
        return out.isEmpty() ? "本条的原文对照暂缺。" : out + "。";
    }

    private List<String> jsonList(Object raw) {
        List<String> list = new ArrayList<>();
        if (raw == null) {
            return list;
        }
        try {
            JsonNode node = json.readTree(raw.toString());
            if (node.isArray()) {
                node.forEach(n -> {
                    String t = n.asText();
                    if (!t.isBlank()) {
                        list.add(t);
                    }
                });
            }
        } catch (Exception e) {
            // 脏 JSON 不该让报告页 500：返回空列表，页面显示"无"
        }
        return list;
    }

    /** yyyy-MM-dd HH:mm → 今天 20:14 / 昨天 19:50 / 10-09 20:14 */
    private String friendlyTime(String raw) {
        if (raw == null || raw.length() < 16) {
            return "";
        }
        try {
            LocalDateTime t = LocalDateTime.parse(raw.replace(' ', 'T'));
            LocalDate today = LocalDate.now(ZoneId.of(zone));
            if (t.toLocalDate().equals(today)) {
                return "今天 " + t.format(HH_MM);
            }
            if (t.toLocalDate().equals(today.minusDays(1))) {
                return "昨天 " + t.format(HH_MM);
            }
            return t.format(MM_DD_HM);
        } catch (RuntimeException e) {
            return raw;
        }
    }

    private static String fmtDose(Object dose) {
        try {
            double d = Double.parseDouble(dose.toString());
            return d == Math.rint(d) ? String.valueOf((long) d) : String.valueOf(d);
        } catch (NumberFormatException e) {
            return dose.toString();
        }
    }

    private static String trim(String s, int max) {
        String t = s.trim();
        return t.length() <= max ? t : t.substring(0, max) + "…";
    }

    /** 掐掉末尾句号，避免和拼接的「。」叠成「。。」 */
    private static String stripTail(String s) {
        return s.replaceAll("[。；;.\\s]+$", "");
    }

    private static String str(Object v) {
        return v == null ? null : v.toString();
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    private static int intOf(Object v) {
        if (v == null) {
            return 0;
        }
        if (v instanceof Number n) {
            return n.intValue();
        }
        try {
            return (int) Math.round(Double.parseDouble(v.toString()));
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
