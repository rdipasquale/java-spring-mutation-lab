package com.example.mutationlab.order;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;

import java.time.Instant;

public record PurchaseOrderDetails(
        Long id,
        long subtotalCents,
        CustomerTier customerTier,
        boolean firstPurchase,
        String couponCode,
        DeliveryMethod deliveryMethod,
        long discountCents,
        long netCents,
        long shippingCents,
        long totalCents,
        Instant createdAt
) {
}
