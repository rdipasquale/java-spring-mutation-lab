package com.example.mutationlab.pricing;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;

import java.util.Objects;

/**
 * Intentionally small business policy used as the mutation-testing target.
 *
 * Business rules:
 * - PREMIUM receives 10 percent and VIP receives 15 percent.
 * - A first purchase adds 5 percentage points.
 * - Coupon SAVE10 subtracts 1000 cents.
 * - Total discount is capped at 30 percent of the subtotal.
 * - Pickup is free. Home shipping is free from 10000 net cents.
 * - Otherwise standard shipping costs 700 cents and express costs 1500 cents.
 */
public final class PricingPolicy {

    public PriceBreakdown calculate(OrderDraft draft) {
        Objects.requireNonNull(draft, "draft is required");

        if (draft.subtotalCents() <= 0) {
            throw new IllegalArgumentException("subtotalCents must be greater than zero");
        }

        int discountPercent = tierDiscount(draft.customerTier());
        if (draft.firstPurchase()) {
            discountPercent += 5;
        }

        long percentageDiscount = draft.subtotalCents() * discountPercent / 100;
        long couponDiscount = couponDiscount(draft.couponCode());
        long maximumDiscount = draft.subtotalCents() * 30 / 100;
        long discount = Math.min(percentageDiscount + couponDiscount, maximumDiscount);

        long net = draft.subtotalCents() - discount;
        long shipping = shippingCost(net, draft.deliveryMethod());
        long total = net + shipping;

        return new PriceBreakdown(
                draft.subtotalCents(),
                discount,
                net,
                shipping,
                total
        );
    }

    private int tierDiscount(CustomerTier customerTier) {
        return switch (customerTier) {
            case BASIC -> 0;
            case PREMIUM -> 10;
            case VIP -> 15;
        };
    }

    private long couponDiscount(String couponCode) {
        long discount = 0;
        if (couponCode != null && couponCode.equalsIgnoreCase("SAVE10")) {
            discount = 1_000;
        }
        return discount;
    }

    private long shippingCost(long netCents, DeliveryMethod deliveryMethod) {
        if (deliveryMethod == DeliveryMethod.PICKUP || netCents >= 10_000) {
            return 0;
        }

        long shipping = 700;
        if (deliveryMethod == DeliveryMethod.EXPRESS) {
            shipping += 800;
        }
        return shipping;
    }
}
