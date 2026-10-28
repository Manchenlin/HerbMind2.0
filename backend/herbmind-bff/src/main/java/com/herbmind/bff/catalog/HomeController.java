package com.herbmind.bff.catalog;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;

/**
 * 首页：GET /api/biz/home —— 聚合 catalog（统计 / 书架 / 今日方证）+ 图谱预览。
 * 域1 维护本控制器。
 */
@RestController
@RequestMapping("/api/biz")
public class HomeController {

    private final HomeService homeService;

    public HomeController(HomeService homeService) {
        this.homeService = homeService;
    }

    @GetMapping("/home")
    public R<HomeVO> home() {
        return R.ok(homeService.home());
    }
}
