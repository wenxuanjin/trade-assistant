package com.tradeassistant.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

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
}
