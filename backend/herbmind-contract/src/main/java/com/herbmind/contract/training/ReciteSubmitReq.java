package com.herbmind.contract.training;

/**
 * 背诵提交（POST /api/biz/train/recite）。
 *
 * @param quoteId 背的是哪条
 * @param text    默写内容（原文或白话都行，前端不区分）
 */
public record ReciteSubmitReq(String quoteId, String text) {
}
