package com.example.mutationlab.api;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import com.example.mutationlab.order.PurchaseOrderDetails;

import java.time.Instant;

public record OrderResponse(
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
    static OrderResponse from(PurchaseOrderDetails details) {
        return new OrderResponse(
                details.id(),
                details.subtotalCents(),
                details.customerTier(),
                details.firstPurchase(),
                details.couponCode(),
                details.deliveryMethod(),
                details.discountCents(),
                details.netCents(),
                details.shippingCents(),
                details.totalCents(),
                details.createdAt()
        );
    }
}
