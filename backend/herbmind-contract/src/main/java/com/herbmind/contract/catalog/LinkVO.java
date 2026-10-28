package com.herbmind.contract.catalog;

/**
 * 极简引用（id + 名称），用于条文 ↔ 方剂 / 医案互链。
 */
public record LinkVO(String id, String name) {
}
