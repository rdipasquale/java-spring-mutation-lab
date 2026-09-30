package com.example.mutationlab.order;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;

import java.util.Objects;

public record CreatePurchaseOrderCommand(
        long subtotalCents,
        CustomerTier customerTier,
        boolean firstPurchase,
        String couponCode,
        DeliveryMethod deliveryMethod
) {
    public CreatePurchaseOrderCommand {
        Objects.requireNonNull(customerTier, "customerTier is required");
        Objects.requireNonNull(deliveryMethod, "deliveryMethod is required");
    }
}
