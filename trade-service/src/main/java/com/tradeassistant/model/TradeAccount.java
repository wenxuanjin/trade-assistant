package com.tradeassistant.model;

/** 订单支付账户的内存数据，字段与 Python TradeAccount 对齐。 */
public record TradeAccount(
        String orderId,
        boolean found,
        String accountId,
        String accountName,
        String paymentChannel,
        String maskedAccountNo,
        String currency
) {
}
