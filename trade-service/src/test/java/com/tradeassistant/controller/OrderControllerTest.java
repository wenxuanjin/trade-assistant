package com.tradeassistant.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class OrderControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void returnsShippedOrder() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-1001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1001"))
                .andExpect(jsonPath("$.status").value("shipped"))
                .andExpect(jsonPath("$.item").value("Mechanical Keyboard"))
                .andExpect(jsonPath("$.amount").value("599.00"));
    }

    @Test
    void returnsPendingOrder() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-1002"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1002"))
                .andExpect(jsonPath("$.status").value("pending"))
                .andExpect(jsonPath("$.item").value("USB-C Cable"))
                .andExpect(jsonPath("$.amount").value("29.00"));
    }

    @Test
    void returnsNotFoundForMissingOrder() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-9999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Order not found: ORD-9999"));
    }

    @Test
    void returnsShippedTradeFlow() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-1001/trade-flow"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1001"))
                .andExpect(jsonPath("$.found").value(true))
                .andExpect(jsonPath("$.currentStatus").value("shipped"))
                .andExpect(jsonPath("$.steps[0].step").value(1))
                .andExpect(jsonPath("$.steps[0].name").value("created"))
                .andExpect(jsonPath("$.steps[0].status").value("done"))
                .andExpect(jsonPath("$.steps[0].occurredAt").value("2026-09-20 10:00:00"))
                .andExpect(jsonPath("$.steps[1].name").value("paid"))
                .andExpect(jsonPath("$.steps[1].status").value("done"))
                .andExpect(jsonPath("$.steps[1].occurredAt").value("2026-09-20 10:05:00"))
                .andExpect(jsonPath("$.steps[2].name").value("shipped"))
                .andExpect(jsonPath("$.steps[2].status").value("done"))
                .andExpect(jsonPath("$.steps[2].occurredAt").value("2026-09-21 09:00:00"))
                .andExpect(jsonPath("$.steps[3].name").value("delivered"))
                .andExpect(jsonPath("$.steps[3].status").value("pending"))
                .andExpect(jsonPath("$.steps[3].occurredAt").value(nullValue()));
    }

    @Test
    void returnsPendingTradeFlow() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-1002/trade-flow"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1002"))
                .andExpect(jsonPath("$.found").value(true))
                .andExpect(jsonPath("$.currentStatus").value("pending"))
                .andExpect(jsonPath("$.steps[0].name").value("created"))
                .andExpect(jsonPath("$.steps[0].status").value("done"))
                .andExpect(jsonPath("$.steps[0].occurredAt").value("2026-09-26 14:00:00"))
                .andExpect(jsonPath("$.steps[1].name").value("paid"))
                .andExpect(jsonPath("$.steps[1].status").value("pending"))
                .andExpect(jsonPath("$.steps[1].occurredAt").value(nullValue()))
                .andExpect(jsonPath("$.steps[2].name").value("shipped"))
                .andExpect(jsonPath("$.steps[2].status").value("pending"))
                .andExpect(jsonPath("$.steps[3].name").value("delivered"))
                .andExpect(jsonPath("$.steps[3].status").value("pending"));
    }

    @Test
    void returnsNotFoundForMissingTradeFlow() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-9999/trade-flow"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Order not found: ORD-9999"));
    }

    @Test
    void returnsAlipayTradeAccount() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-1001/trade-account"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1001"))
                .andExpect(jsonPath("$.found").value(true))
                .andExpect(jsonPath("$.accountId").value("ACC-8801"))
                .andExpect(jsonPath("$.accountName").value("Logan Zhang"))
                .andExpect(jsonPath("$.paymentChannel").value("alipay"))
                .andExpect(jsonPath("$.maskedAccountNo").value("138****1001"))
                .andExpect(jsonPath("$.currency").value("CNY"));
    }

    @Test
    void returnsWechatTradeAccount() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-1002/trade-account"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("ORD-1002"))
                .andExpect(jsonPath("$.found").value(true))
                .andExpect(jsonPath("$.accountId").value("ACC-8802"))
                .andExpect(jsonPath("$.accountName").value("Logan Zhang"))
                .andExpect(jsonPath("$.paymentChannel").value("wechat_pay"))
                .andExpect(jsonPath("$.maskedAccountNo").value("138****1002"))
                .andExpect(jsonPath("$.currency").value("CNY"));
    }

    @Test
    void returnsNotFoundForMissingTradeAccount() throws Exception {
        mockMvc.perform(get("/api/orders/ORD-9999/trade-account"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Order not found: ORD-9999"));
    }
}
