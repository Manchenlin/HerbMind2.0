package com.herbmind.contract.catalog;

import java.math.BigDecimal;

/**
 * 药味（君臣佐使）。dose 为数字，前端自行拼单位。
 */
public record HerbVO(
        String name,
        BigDecimal dose,
        String unit,
        String role,
        int seq) {
}
