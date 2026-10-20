package com.tradeassistant.service;

import com.tradeassistant.dto.OrderResponse;
import com.tradeassistant.dto.TradeAccountResponse;
import com.tradeassistant.dto.TradeFlowResponse;
import com.tradeassistant.dto.TradeFlowStepResponse;
import com.tradeassistant.exception.OrderNotFoundException;
import com.tradeassistant.model.Order;
import com.tradeassistant.model.TradeAccount;
import com.tradeassistant.model.TradeFlow;
import com.tradeassistant.repository.OrderRepository;
import com.tradeassistant.repository.TradeAccountRepository;
import com.tradeassistant.repository.TradeFlowRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final TradeFlowRepository tradeFlowRepository;
    private final TradeAccountRepository tradeAccountRepository;

    public OrderService(
            OrderRepository orderRepository,
            TradeFlowRepository tradeFlowRepository,
            TradeAccountRepository tradeAccountRepository
    ) {
        this.orderRepository = orderRepository;
        this.tradeFlowRepository = tradeFlowRepository;
        this.tradeAccountRepository = tradeAccountRepository;
    }

    public OrderResponse getOrder(String orderId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new OrderNotFoundException(orderId));
        return new OrderResponse(order.orderId(), order.status(), order.item(), order.amount());
    }

    public TradeFlowResponse getTradeFlow(String orderId) {
        TradeFlow flow = tradeFlowRepository.findByOrderId(orderId)
                .orElseThrow(() -> new OrderNotFoundException(orderId));
        List<TradeFlowStepResponse> steps = flow.steps().stream()
                .map(step -> new TradeFlowStepResponse(step.step(), step.name(), step.status(), step.occurredAt()))
                .toList();
        return new TradeFlowResponse(flow.orderId(), flow.found(), flow.currentStatus(), steps);
    }

    /** 查询订单支付账户；订单不存在时沿用现有 404。 */
    public TradeAccountResponse getTradeAccount(String orderId) {
        TradeAccount account = tradeAccountRepository.findByOrderId(orderId)
                .orElseThrow(() -> new OrderNotFoundException(orderId));
        return new TradeAccountResponse(
                account.orderId(),
                account.found(),
                account.accountId(),
                account.accountName(),
                account.paymentChannel(),
                account.maskedAccountNo(),
                account.currency()
        );
    }
}
