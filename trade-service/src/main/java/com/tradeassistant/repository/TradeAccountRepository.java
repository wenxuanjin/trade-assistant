package com.tradeassistant.repository;

import com.tradeassistant.model.TradeAccount;
import org.springframework.stereotype.Repository;

import java.util.Map;
import java.util.Optional;

/** 支付账户的内存 Mock，后续可换成真实查询。 */
@Repository
public class TradeAccountRepository {

    private final Map<String, TradeAccount> accounts = Map.of(
            "ORD-1001", new TradeAccount(
                    "ORD-1001", true, "ACC-8801", "Logan Zhang", "alipay", "138****1001", "CNY"
            ),
            "ORD-1002", new TradeAccount(
                    "ORD-1002", true, "ACC-8802", "Logan Zhang", "wechat_pay", "138****1002", "CNY"
            )
    );

    public Optional<TradeAccount> findByOrderId(String orderId) {
        return Optional.ofNullable(accounts.get(orderId));
    }
}
