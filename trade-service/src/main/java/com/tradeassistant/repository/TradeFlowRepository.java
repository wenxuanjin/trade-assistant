package com.tradeassistant.repository;

import com.tradeassistant.model.TradeFlow;
import com.tradeassistant.model.TradeFlowStep;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class TradeFlowRepository {

    private final Map<String, TradeFlow> flows = Map.of(
            "ORD-1001", new TradeFlow("ORD-1001", true, "shipped", List.of(
                    new TradeFlowStep(1, "created", "done", "2026-09-20 10:00:00"),
                    new TradeFlowStep(2, "paid", "done", "2026-09-20 10:05:00"),
                    new TradeFlowStep(3, "shipped", "done", "2026-09-21 09:00:00"),
                    new TradeFlowStep(4, "delivered", "pending", null)
            )),
            "ORD-1002", new TradeFlow("ORD-1002", true, "pending", List.of(
                    new TradeFlowStep(1, "created", "done", "2026-09-26 14:00:00"),
                    new TradeFlowStep(2, "paid", "pending", null),
                    new TradeFlowStep(3, "shipped", "pending", null),
                    new TradeFlowStep(4, "delivered", "pending", null)
            ))
    );

    public Optional<TradeFlow> findByOrderId(String orderId) {
        return Optional.ofNullable(flows.get(orderId));
    }
}
