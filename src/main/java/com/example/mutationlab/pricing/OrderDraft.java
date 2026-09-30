package com.example.mutationlab.pricing;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;

import java.util.Objects;

public record OrderDraft(
        long subtotalCents,
        CustomerTier customerTier,
        boolean firstPurchase,
        String couponCode,
        DeliveryMethod deliveryMethod
) {
    public OrderDraft {
        Objects.requireNonNull(customerTier, "customerTier is required");
        Objects.requireNonNull(deliveryMethod, "deliveryMethod is required");
    }
}
