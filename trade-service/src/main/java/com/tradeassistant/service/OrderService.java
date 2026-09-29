package com.tradeassistant.service;

import com.tradeassistant.dto.OrderResponse;
import com.tradeassistant.exception.OrderNotFoundException;
import com.tradeassistant.model.Order;
import com.tradeassistant.repository.OrderRepository;
import org.springframework.stereotype.Service;

@Service
public class OrderService {

    private final OrderRepository orderRepository;

    public OrderService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    public OrderResponse getOrder(String orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new OrderNotFoundException(orderId));
        return new OrderResponse(order.orderId(), order.status(), order.item(), order.amount());
    }
}
