package com.herbmind.svc.training.controller;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.contract.training.AnswerScoreVO;
import com.herbmind.contract.training.BlindboxAnswerVO;
import com.herbmind.contract.training.BlindboxVO;
import com.herbmind.contract.training.FormulaLibVO;
import com.herbmind.contract.training.MeDashboardVO;
import com.herbmind.contract.training.MeProfileVO;
import com.herbmind.contract.training.MeReportVO;
import com.herbmind.contract.training.PathVO;
import com.herbmind.contract.training.PracticeQuestionVO;
import com.herbmind.contract.training.ReciteResultVO;
import com.herbmind.contract.training.ReciteSubmitReq;
import com.herbmind.contract.training.ReciteVO;
import com.herbmind.contract.training.SubmitAnswerReq;
import com.herbmind.contract.training.TrainOptionsVO;
import com.herbmind.contract.training.WrongBookVO;
import com.herbmind.svc.training.service.BlindboxService;
import com.herbmind.svc.training.service.DashboardService;
import com.herbmind.svc.training.service.MeLibraryService;
import com.herbmind.svc.training.service.PracticeService;
import com.herbmind.svc.training.service.ProfileService;
import com.herbmind.svc.training.service.ReciteService;
import com.herbmind.svc.training.service.ReportService;

/**
 * 内部接口（只给 BFF 调，不对外暴露）。
 * 返回**裸 DTO**（不包 R）—— 统一包装由 BFF 负责，与 svc-catalog / svc-identity 一致。
 *
 * 路径对齐 09 契约第 6 节；契约里没写的（盲盒 / 背诵 / 报告 / 方证库 / 路径）
 * 按同一规范补在 /internal/training 下，并在 09 契约的变更记录里登记。
 */
@RestController
@RequestMapping("/internal/training")
public class InternalTrainingController {

    private final DashboardService dashboardService;
    private final ProfileService profileService;
    private final PracticeService practiceService;
    private final BlindboxService blindboxService;
    private final ReciteService reciteService;
    private final ReportService reportService;
    private final MeLibraryService meLibraryService;

    public InternalTrainingController(DashboardService dashboardService,
                                      ProfileService profileService,
                                      PracticeService practiceService,
                                      BlindboxService blindboxService,
                                      ReciteService reciteService,
                                      ReportService reportService,
                                      MeLibraryService meLibraryService) {
        this.dashboardService = dashboardService;
        this.profileService = profileService;
        this.practiceService = practiceService;
        this.blindboxService = blindboxService;
        this.reciteService = reciteService;
        this.reportService = reportService;
        this.meLibraryService = meLibraryService;
    }

    /** 「我的 · 总览」统计部分；userId 由 BFF 从网关透传的 X-User-Id 带入。 */
    @GetMapping("/dashboard")
    public MeDashboardVO dashboard(@RequestParam("userId") String userId) {
        requireUser(userId);
        return dashboardService.dashboard(userId);
    }

    /** 学习档案：按经典拆解 + 路径 + 薄弱点（契约 GET /api/biz/me/profile）。 */
    @GetMapping("/profile")
    public MeProfileVO profile(@RequestParam("userId") String userId) {
        requireUser(userId);
        return profileService.profile(userId);
    }

    /** 练习台选项：可练的书 / 单元 / 模式 + 最近练习。 */
    @GetMapping("/options")
    public TrainOptionsVO options(@RequestParam("userId") String userId) {
        requireUser(userId);
        return practiceService.options(userId);
    }

    /** 开练习会话并出题（契约 POST /api/biz/train/session）。 */
    @PostMapping("/session")
    public PracticeQuestionVO startSession(@RequestParam("userId") String userId,
                                           @RequestParam("nodeRef") String nodeRef,
                                           @RequestParam(value = "mode", required = false) String mode,
                                           @RequestParam(value = "formulaId", required = false) String formulaId) {
        requireUser(userId);
        return practiceService.start(userId, nodeRef, mode, formulaId);
    }

    /** 提交作答并评分（契约 POST /api/biz/train/answer；BFF 侧负责编排）。 */
    @PostMapping("/answer")
    public AnswerScoreVO submit(@RequestParam("userId") String userId,
                                @RequestBody SubmitAnswerReq req) {
        requireUser(userId);
        return practiceService.submit(userId, req);
    }

    // ------------------------------------------------------------------ 案例盲盒

    /** 抽一个盲盒：只读，不建会话（没作答不该留空记录）。 */
    @PostMapping("/blindbox")
    public BlindboxVO blindbox(@RequestParam("userId") String userId) {
        requireUser(userId);
        return blindboxService.draw(userId);
    }

    /** 揭晓原著答案。formulaId 可选，带上才有处方明细。 */
    @GetMapping("/blindbox/{caseId}/answer")
    public BlindboxAnswerVO blindboxAnswer(@PathVariable("caseId") String caseId,
                                           @RequestParam(value = "formulaId", required = false) String formulaId) {
        return blindboxService.reveal(caseId, formulaId);
    }

    // ------------------------------------------------------------------ 背诵打卡

    @GetMapping("/recite")
    public ReciteVO recite(@RequestParam("userId") String userId) {
        requireUser(userId);
        return reciteService.list(userId);
    }

    @PostMapping("/recite")
    public ReciteResultVO submitRecite(@RequestParam("userId") String userId,
                                       @RequestBody ReciteSubmitReq req) {
        requireUser(userId);
        return reciteService.submit(userId, req);
    }

    // ------------------------------------------------------------------ 评分报告

    @GetMapping("/report/{answerId}")
    public MeReportVO report(@RequestParam("userId") String userId,
                             @PathVariable("answerId") String answerId) {
        requireUser(userId);
        return reportService.report(userId, answerId);
    }

    // ------------------------------------------------ 错题本 / 方证库 / 学习路径

    @GetMapping("/wrong-book")
    public WrongBookVO wrongBook(@RequestParam("userId") String userId) {
        requireUser(userId);
        return meLibraryService.wrongBook(userId);
    }

    @DeleteMapping("/wrong-book/{unitRef}")
    public WrongBookVO removeWrong(@RequestParam("userId") String userId,
                                   @PathVariable("unitRef") String unitRef) {
        requireUser(userId);
        return meLibraryService.removeWrong(userId, unitRef);
    }

    @GetMapping("/collection")
    public FormulaLibVO collection(@RequestParam("userId") String userId) {
        requireUser(userId);
        return meLibraryService.collection(userId);
    }

    @GetMapping("/path")
    public PathVO path(@RequestParam("userId") String userId) {
        requireUser(userId);
        return meLibraryService.path(userId);
    }

    private void requireUser(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("缺少用户上下文（userId）");
        }
    }
}
