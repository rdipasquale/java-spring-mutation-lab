package com.example.mutationlab.pricing;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PricingPolicyTest {

    private final PricingPolicy policy = new PricingPolicy();

    @ParameterizedTest(name = "{index}: tier={1}, first={2}, coupon={3}, delivery={4}")
    @MethodSource("representativeOrders")
    void calculatesRepresentativeOrders(
            long subtotal,
            CustomerTier tier,
            boolean firstPurchase,
            String coupon,
            DeliveryMethod delivery,
            boolean shouldHaveDiscount,
            ShippingExpectation shippingExpectation
    ) {
        PriceBreakdown result = policy.calculate(
                new OrderDraft(subtotal, tier, firstPurchase, coupon, delivery)
        );

        assertAll(
                () -> assertNotNull(result),
                () -> assertEquals(subtotal, result.subtotalCents()),
                () -> assertTrue(result.discountCents() >= 0),
                () -> assertTrue(result.discountCents() < subtotal),
                () -> assertEquals(subtotal - result.discountCents(), result.netCents()),
                () -> assertEquals(result.netCents() + result.shippingCents(), result.totalCents()),
                () -> assertTrue(result.totalCents() > 0),
                () -> assertDiscountPresence(result, shouldHaveDiscount),
                () -> assertShippingPresence(result, shippingExpectation)
        );
    }

    @ParameterizedTest
    @MethodSource("invalidSubtotals")
    void rejectsInvalidSubtotals(long subtotal) {
        OrderDraft draft = new OrderDraft(
                subtotal,
                CustomerTier.BASIC,
                false,
                null,
                DeliveryMethod.STANDARD
        );

        assertThrows(IllegalArgumentException.class, () -> policy.calculate(draft));
    }

    @Test
    void rejectsNullDraft() {
        assertThrows(NullPointerException.class, () -> policy.calculate(null));
    }

    @Test
    void neverDiscountsMoreThanThirtyPercent() {
        long subtotal = 3_000;
        PriceBreakdown result = policy.calculate(new OrderDraft(
                subtotal,
                CustomerTier.VIP,
                true,
                "SAVE10",
                DeliveryMethod.EXPRESS
        ));

        assertTrue(result.discountCents() <= subtotal * 30 / 100);
    }

    private static Stream<Arguments> representativeOrders() {
        return Stream.of(
                Arguments.of(5_000L, CustomerTier.BASIC, false, null,
                        DeliveryMethod.STANDARD, false, ShippingExpectation.PAID),
                Arguments.of(5_000L, CustomerTier.BASIC, false, null,
                        DeliveryMethod.EXPRESS, false, ShippingExpectation.PAID),
                Arguments.of(5_000L, CustomerTier.BASIC, false, null,
                        DeliveryMethod.PICKUP, false, ShippingExpectation.FREE),
                Arguments.of(20_000L, CustomerTier.PREMIUM, false, null,
                        DeliveryMethod.STANDARD, true, ShippingExpectation.FREE),
                Arguments.of(15_000L, CustomerTier.VIP, false, null,
                        DeliveryMethod.STANDARD, true, ShippingExpectation.FREE),
                Arguments.of(8_000L, CustomerTier.BASIC, true, null,
                        DeliveryMethod.STANDARD, true, ShippingExpectation.PAID),
                Arguments.of(9_000L, CustomerTier.BASIC, false, "save10",
                        DeliveryMethod.EXPRESS, true, ShippingExpectation.PAID),
                Arguments.of(9_000L, CustomerTier.VIP, true, "SAVE10",
                        DeliveryMethod.EXPRESS, true, ShippingExpectation.PAID),
                Arguments.of(12_000L, CustomerTier.BASIC, false, "NOT-A-COUPON",
                        DeliveryMethod.STANDARD, false, ShippingExpectation.FREE)
        );
    }

    private static Stream<Long> invalidSubtotals() {
        return Stream.of(0L, -1L, -10_000L);
    }

    private static void assertDiscountPresence(PriceBreakdown result, boolean shouldHaveDiscount) {
        if (shouldHaveDiscount) {
            assertTrue(result.discountCents() > 0);
        } else {
            assertEquals(0, result.discountCents());
        }
    }

    private static void assertShippingPresence(
            PriceBreakdown result,
            ShippingExpectation expectation
    ) {
        if (expectation == ShippingExpectation.FREE) {
            assertEquals(0, result.shippingCents());
        } else {
            assertTrue(result.shippingCents() > 0);
        }
    }

    private enum ShippingExpectation {
        FREE,
        PAID
    }
}
