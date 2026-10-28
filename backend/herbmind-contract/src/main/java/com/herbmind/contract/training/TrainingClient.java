package com.herbmind.contract.training;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * svc-training 内部契约（OpenFeign 4.x：禁类级 @RequestMapping，用 path 属性）。
 *
 * /internal/** 返回**裸 DTO**（不包 R），由 BFF 统一包 R 给前端。
 * url 默认本地直连 :8084；上 Nacos 后用 herbmind.svc-training-url 覆盖。
 */
@FeignClient(name = "svc-training", path = "/internal/training",
        url = "${herbmind.svc-training-url:http://localhost:8084}")
public interface TrainingClient {

    /** 「我的 · 总览」的统计部分（user 字段由 BFF 补）。 */
    @GetMapping("/dashboard")
    MeDashboardVO dashboard(@RequestParam("userId") String userId);

    /** 学习档案：按经典拆解 + 学习路径 + 薄弱点。 */
    @GetMapping("/profile")
    MeProfileVO profile(@RequestParam("userId") String userId);

    /** 练习台选项：可练的书 / 单元 / 模式 + 最近练习。 */
    @GetMapping("/options")
    TrainOptionsVO options(@RequestParam("userId") String userId);

    /** 开练习会话并出题（题面已藏答案）。formulaId 给定则固定出这道题（盲盒「我也答一遍」用）。 */
    @PostMapping("/session")
    PracticeQuestionVO startSession(@RequestParam("userId") String userId,
                                    @RequestParam("nodeRef") String nodeRef,
                                    @RequestParam(value = "mode", required = false) String mode,
                                    @RequestParam(value = "formulaId", required = false) String formulaId);

    /** 提交作答并评分。 */
    @PostMapping("/answer")
    AnswerScoreVO submit(@RequestParam("userId") String userId,
                         @RequestBody SubmitAnswerReq req);

    /* ------------------------------- 案例盲盒 ------------------------------- */

    /** 随机抽一个医案（不建会话，题面不含方名）。 */
    @PostMapping("/blindbox")
    BlindboxVO drawBlindbox(@RequestParam("userId") String userId);

    /** 揭晓原著答案（按案例 ID，与是否作答无关）。formulaId 可选，带上才有处方明细。 */
    @GetMapping("/blindbox/{caseId}/answer")
    BlindboxAnswerVO blindboxAnswer(@PathVariable("caseId") String caseId,
                                    @RequestParam(value = "formulaId", required = false) String formulaId);

    /* ------------------------------- 背诵打卡 ------------------------------- */

    /** 待背 / 到期条文 + 打卡统计。 */
    @GetMapping("/recite")
    ReciteVO recite(@RequestParam("userId") String userId);

    /** 提交默写（字面比对，确定性评分）。 */
    @PostMapping("/recite")
    ReciteResultVO submitRecite(@RequestParam("userId") String userId,
                                @RequestBody ReciteSubmitReq req);

    /* ------------------------------- 评分报告 ------------------------------- */

    /** 单次作答的完整报告（含原著对照与累计能力画像）。 */
    @GetMapping("/report/{answerId}")
    MeReportVO report(@RequestParam("userId") String userId,
                      @PathVariable("answerId") String answerId);

    /* ----------------------- 错题本 / 方证库 / 学习路径 ----------------------- */

    @GetMapping("/wrong-book")
    WrongBookVO wrongBook(@RequestParam("userId") String userId);

    /** 移出错题本（练到 60 分以上后由用户主动移除）。 */
    @DeleteMapping("/wrong-book/{unitRef}")
    WrongBookVO removeWrong(@RequestParam("userId") String userId,
                            @PathVariable("unitRef") String unitRef);

    @GetMapping("/collection")
    FormulaLibVO collection(@RequestParam("userId") String userId);

    @GetMapping("/path")
    PathVO path(@RequestParam("userId") String userId);
}
