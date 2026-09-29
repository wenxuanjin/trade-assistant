package com.tradeassistant.model;

public record Order(String orderId, String status, String item, String amount) {
}
