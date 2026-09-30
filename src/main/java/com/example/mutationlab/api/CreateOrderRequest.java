package com.example.mutationlab.api;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import com.example.mutationlab.order.CreatePurchaseOrderCommand;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateOrderRequest(
        @Min(value = 1, message = "subtotalCents must be greater than zero")
        long subtotalCents,

        @NotNull
        CustomerTier customerTier,

        boolean firstPurchase,

        @Size(max = 32)
        String couponCode,

        @NotNull
        DeliveryMethod deliveryMethod
) {
    CreatePurchaseOrderCommand toCommand() {
        return new CreatePurchaseOrderCommand(
                subtotalCents,
                customerTier,
                firstPurchase,
                couponCode,
                deliveryMethod
        );
    }
}
