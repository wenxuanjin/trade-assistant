package com.tradeassistant.dto;

public record OrderResponse(String orderId, String status, String item, String amount) {
}
