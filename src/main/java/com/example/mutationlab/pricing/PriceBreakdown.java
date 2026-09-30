package com.example.mutationlab.pricing;

public record PriceBreakdown(
        long subtotalCents,
        long discountCents,
        long netCents,
        long shippingCents,
        long totalCents
) {
}
