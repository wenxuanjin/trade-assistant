package com.tradeassistant.repository;

import com.tradeassistant.model.Order;
import org.springframework.stereotype.Repository;

import java.util.Map;
import java.util.Optional;

@Repository
public class OrderRepository {

    private final Map<String, Order> orders = Map.of(
            "ORD-1001", new Order("ORD-1001", "shipped", "Mechanical Keyboard", "599.00"),
            "ORD-1002", new Order("ORD-1002", "pending", "USB-C Cable", "29.00")
    );

    public Optional<Order> findById(String orderId) {
        return Optional.ofNullable(orders.get(orderId));
    }
}
