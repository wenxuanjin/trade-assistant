package com.tradeassistant.controller;

import com.tradeassistant.dto.OrderResponse;
import com.tradeassistant.dto.TradeAccountResponse;
import com.tradeassistant.dto.TradeFlowResponse;
import com.tradeassistant.service.OrderService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @GetMapping("/{orderId}")
    public OrderResponse getOrder(@PathVariable String orderId) {
        System.out.println("getOrder: " + orderId);
        return orderService.getOrder(orderId);
    }

    @GetMapping("/{orderId}/trade-flow")
    public TradeFlowResponse getTradeFlow(@PathVariable String orderId) {
        return orderService.getTradeFlow(orderId);
    }

    /** 查询订单支付账户。 */
    @GetMapping("/{orderId}/trade-account")
    public TradeAccountResponse getTradeAccount(@PathVariable String orderId) {
        return orderService.getTradeAccount(orderId);
    }
}
