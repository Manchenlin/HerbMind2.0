package com.herbmind.bff.train;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.training.AnswerScoreVO;
import com.herbmind.contract.training.BlindboxAnswerVO;
import com.herbmind.contract.training.BlindboxVO;
import com.herbmind.contract.training.MeReportVO;
import com.herbmind.contract.training.PracticeQuestionVO;
import com.herbmind.contract.training.ReciteResultVO;
import com.herbmind.contract.training.ReciteSubmitReq;
import com.herbmind.contract.training.ReciteVO;
import com.herbmind.contract.training.SubmitAnswerReq;
import com.herbmind.contract.training.TrainOptionsVO;
import com.herbmind.contract.training.TrainingClient;

/**
 * BFF：练习（域2，包 bff/train）。
 *
 * 与「我的」一样是薄层：不做统计、不做评分，只把 X-User-Id 透传下去并包上 R。
 * 评分口径在 svc-training（确定性规则），将来接 Agent 语义评分也换在那一层，BFF 不用改。
 */
@RestController
@RequestMapping("/api/biz/train")
public class TrainController {

    private final TrainingClient training;

    public TrainController(TrainingClient training) {
        this.training = training;
    }

    /** 练习台选项（书 / 单元 / 模式 + 最近练习）。 */
    @GetMapping("/options")
    public R<TrainOptionsVO> options(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(training.options(requireUser(userId)));
    }

    /**
     * 开练习会话（契约 POST /api/biz/train/session）。
     * ref 走 body 还是 query？契约写的是 POST，字段未细化；这里用 query，前端更好拼。
     */
    @PostMapping("/session")
    public R<PracticeQuestionVO> startSession(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @RequestParam("nodeRef") String nodeRef,
            @RequestParam(value = "mode", required = false) String mode,
            @RequestParam(value = "formulaId", required = false) String formulaId) {
        return R.ok(training.startSession(requireUser(userId), nodeRef, mode, formulaId));
    }

    /**
     * 契约 GET /api/biz/train/unit/{ref} 的等价实现：
     * 题面必须开一个会话才有 sessionId，所以这里也走 startSession。
     * 保留 path 版本是为了让前端「直接按单元练」的场景读起来自然。
     */
    @GetMapping("/unit/{ref}")
    public R<PracticeQuestionVO> unit(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @PathVariable("ref") String ref,
            @RequestParam(value = "mode", required = false) String mode) {
        return R.ok(training.startSession(requireUser(userId), ref, mode, null));
    }

    /* ------------------------------- 案例盲盒 ------------------------------- */

    /** 抽一个盲盒。只读：不解锁答案、不建会话。 */
    @PostMapping("/blindbox")
    public R<BlindboxVO> blindbox(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        BlindboxVO vo = training.drawBlindbox(requireUser(userId));
        if (vo == null || vo.caseId() == null) {
            throw new IllegalArgumentException("暂时没有可揭晓的医案，换一个试试");
        }
        return R.ok(vo);
    }

    /** 揭晓原著答案。 */
    @GetMapping("/blindbox/{caseId}/answer")
    public R<BlindboxAnswerVO> blindboxAnswer(
            @PathVariable("caseId") String caseId,
            @RequestParam(value = "formulaId", required = false) String formulaId) {
        BlindboxAnswerVO vo = training.blindboxAnswer(caseId, formulaId);
        if (vo == null || vo.formulaName() == null) {
            throw new IllegalArgumentException("该医案没有挂载参考方，换一个盲盒试试");
        }
        return R.ok(vo);
    }

    /* ------------------------------- 背诵打卡 ------------------------------- */

    @GetMapping("/recite")
    public R<ReciteVO> recite(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(training.recite(requireUser(userId)));
    }

    @PostMapping("/recite")
    public R<ReciteResultVO> submitRecite(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @RequestBody ReciteSubmitReq req) {
        ReciteResultVO vo = training.submitRecite(requireUser(userId), req);
        if (vo == null || vo.standard() == null) {
            throw new IllegalArgumentException("判分没有返回结果，请刷新后重试");
        }
        return R.ok(vo);
    }

    /* ------------------------------- 评分报告 ------------------------------- */

    /**
     * 单条作答的报告。
     *
     * ★ 和 /answer 一样要判空：下游出错时返回 HTTP 200 + R{code:4000}，
     *   Feign 不抛异常，而是把错误体反序列化成全 null 的 VO。
     *   不判的话前端拿到 `data:{}`，报告页会显示一堆空白而不是一句人话。
     */
    @GetMapping("/report/{answerId}")
    public R<MeReportVO> report(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @PathVariable("answerId") String answerId) {
        MeReportVO vo = training.report(requireUser(userId), answerId);
        if (vo == null || vo.answerId() == null) {
            throw new IllegalArgumentException("找不到这条答题记录，可能已被清理");
        }
        return R.ok(vo);
    }

    /**
     * 提交作答 → 评分。
     *
     * ★ 为什么要判 answerId 为空：下游 svc-training 的 GlobalExceptionHandler 返回的是
     *   **HTTP 200 + R{code:4000}**，Feign 不会当成错误抛，而是把这个错误体反序列化成一个
     *   全字段 null 的 AnswerScoreVO。不判就会给前端返回 `data:{}`，用户完全不知道发生了什么。
     *   根治要改公共的 GlobalExceptionHandler（跨域），需与组长确认后再动。
     */
    @PostMapping("/answer")
    public R<AnswerScoreVO> answer(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @RequestBody SubmitAnswerReq req) {
        AnswerScoreVO vo = training.submit(requireUser(userId), req);
        if (vo == null || vo.getAnswerId() == null) {
            throw new IllegalArgumentException("评分没有返回结果，请回练习台重新开一题");
        }
        return R.ok(vo);
    }

    private String requireUser(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("缺少用户上下文，请先登录");
        }
        return userId;
    }
}
