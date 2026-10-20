package com.tradeassistant.dto;

/** 支付账户查询的成功响应。 */
public record TradeAccountResponse(
        String orderId,
        boolean found,
        String accountId,
        String accountName,
        String paymentChannel,
        String maskedAccountNo,
        String currency
) {
}
