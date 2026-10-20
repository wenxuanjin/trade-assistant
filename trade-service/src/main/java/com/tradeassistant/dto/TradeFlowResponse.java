package com.tradeassistant.dto;

import java.util.List;

public record TradeFlowResponse(
        String orderId,
        boolean found,
        String currentStatus,
        List<TradeFlowStepResponse> steps
) {
}
