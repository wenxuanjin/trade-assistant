package com.tradeassistant.model;

import java.util.List;

public record TradeFlow(String orderId, boolean found, String currentStatus, List<TradeFlowStep> steps) {
}
