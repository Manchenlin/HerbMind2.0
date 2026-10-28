package com.herbmind.bff.me;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.identity.FavoriteVO;
import com.herbmind.contract.identity.IdentityClient;
import com.herbmind.contract.identity.NoteVO;
import com.herbmind.contract.identity.UserContentReq;
import com.herbmind.contract.training.FormulaLibVO;
import com.herbmind.contract.training.MeDashboardVO;
import com.herbmind.contract.training.MeProfileVO;
import com.herbmind.contract.training.PathVO;
import com.herbmind.contract.training.TrainingClient;
import com.herbmind.contract.training.WrongBookVO;

/**
 * BFF：我的（域2，包 bff/me）。
 *
 * 一个请求聚合两个服务，前端只调一次：
 *   svc-identity  → user / 收藏 / 笔记
 *   svc-training  → stats / radar / 错题本 / 方证库 / 路径
 *
 * 这是 BFF 存在的意义（而不是让前端并发三个接口），但仍然是薄层：
 * 不做任何统计计算，只做拼装。统计口径在 svc-training 里。
 */
@RestController
@RequestMapping("/api/biz/me")
public class MeController {

    private final IdentityClient identity;
    private final TrainingClient training;

    public MeController(IdentityClient identity, TrainingClient training) {
        this.identity = identity;
        this.training = training;
    }

    @GetMapping("/dashboard")
    public R<MeDashboardVO> dashboard(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        String uid = requireUser(userId);
        MeDashboardVO vo = training.dashboard(uid);
        // 统计拿到了，但用户信息没拿到不该让整页失败：头像/昵称属于"可有可无"
        try {
            vo.setUser(identity.me(uid));
        } catch (RuntimeException e) {
            vo.setUser(null);
        }
        return R.ok(vo);
    }

    /**
     * 学习档案（契约 GET /api/biz/me/profile）。
     * 与总览的区别：按经典拆解掌握度、给学习路径、列薄弱点 —— 数据全在 svc-training 里算。
     */
    @GetMapping("/profile")
    public R<MeProfileVO> profile(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(training.profile(requireUser(userId)));
    }

    /* -------------------------------- 收藏夹 -------------------------------- */

    @GetMapping("/favorites")
    public R<FavoriteVO> favorites(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(identity.favorites(requireUser(userId)));
    }

    @PostMapping("/favorites")
    public R<FavoriteVO> addFavorite(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @RequestBody UserContentReq.Favorite req) {
        return R.ok(identity.addFavorite(requireUser(userId), req));
    }

    @DeleteMapping("/favorites/{id}")
    public R<FavoriteVO> removeFavorite(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @PathVariable("id") long id) {
        return R.ok(identity.removeFavorite(requireUser(userId), id));
    }

    /* -------------------------------- 我的笔记 -------------------------------- */

    @GetMapping("/notes")
    public R<NoteVO> notes(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(identity.notes(requireUser(userId)));
    }

    @PostMapping("/notes")
    public R<NoteVO> saveNote(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @RequestBody UserContentReq.Note req) {
        return R.ok(identity.saveNote(requireUser(userId), req));
    }

    @DeleteMapping("/notes/{id}")
    public R<NoteVO> removeNote(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @PathVariable("id") long id) {
        return R.ok(identity.removeNote(requireUser(userId), id));
    }

    /* -------------------------------- 错题本 -------------------------------- */

    @GetMapping("/wrong")
    public R<WrongBookVO> wrong(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(training.wrongBook(requireUser(userId)));
    }

    @DeleteMapping("/wrong/{unitRef}")
    public R<WrongBookVO> removeWrong(
            @RequestHeader(value = "X-User-Id", required = false) String userId,
            @PathVariable("unitRef") String unitRef) {
        return R.ok(training.removeWrong(requireUser(userId), unitRef));
    }

    /* ------------------------------ 我的方证库 ------------------------------ */

    @GetMapping("/collection")
    public R<FormulaLibVO> collection(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(training.collection(requireUser(userId)));
    }

    /* -------------------------------- 学习路径 -------------------------------- */

    @GetMapping("/path")
    public R<PathVO> path(
            @RequestHeader(value = "X-User-Id", required = false) String userId) {
        return R.ok(training.path(requireUser(userId)));
    }

    private String requireUser(String userId) {
        if (userId == null || userId.isBlank()) {
            throw new IllegalArgumentException("缺少用户上下文，请先登录");
        }
        return userId;
    }
}
