package com.example.mutationlab.pricing;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * Optional stronger tests. Activate them with Maven profile solution-tests.
 * They express exact business outcomes rather than broad invariants.
 */
class PricingPolicySpecificationTest {

    private final PricingPolicy policy = new PricingPolicy();

    @Test
    void basicStandardOrderHasExactShippingPrice() {
        assertPrice(
                new OrderDraft(5_000, CustomerTier.BASIC, false, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(5_000, 0, 5_000, 700, 5_700)
        );
    }

    @Test
    void expressAddsExactlyEightHundredCentsToStandardShipping() {
        assertPrice(
                new OrderDraft(5_000, CustomerTier.BASIC, false, null, DeliveryMethod.EXPRESS),
                new PriceBreakdown(5_000, 0, 5_000, 1_500, 6_500)
        );
    }

    @Test
    void pickupIsAlwaysFree() {
        assertPrice(
                new OrderDraft(5_000, CustomerTier.BASIC, false, null, DeliveryMethod.PICKUP),
                new PriceBreakdown(5_000, 0, 5_000, 0, 5_000)
        );
    }

    @Test
    void premiumDiscountIsExactlyTenPercent() {
        assertPrice(
                new OrderDraft(20_000, CustomerTier.PREMIUM, false, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(20_000, 2_000, 18_000, 0, 18_000)
        );
    }

    @Test
    void vipDiscountIsExactlyFifteenPercent() {
        assertPrice(
                new OrderDraft(15_000, CustomerTier.VIP, false, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(15_000, 2_250, 12_750, 0, 12_750)
        );
    }

    @Test
    void firstPurchaseAddsExactlyFivePercentagePoints() {
        assertPrice(
                new OrderDraft(8_000, CustomerTier.BASIC, true, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(8_000, 400, 7_600, 700, 8_300)
        );
    }

    @Test
    void save10SubtractsExactlyOneThousandCentsAndIgnoresCase() {
        assertPrice(
                new OrderDraft(9_000, CustomerTier.BASIC, false, "save10", DeliveryMethod.EXPRESS),
                new PriceBreakdown(9_000, 1_000, 8_000, 1_500, 9_500)
        );
    }

    @Test
    void unknownCouponHasNoEffect() {
        assertPrice(
                new OrderDraft(9_000, CustomerTier.BASIC, false, "NOPE", DeliveryMethod.STANDARD),
                new PriceBreakdown(9_000, 0, 9_000, 700, 9_700)
        );
    }

    @Test
    void combinedDiscountIsCappedAtExactlyThirtyPercent() {
        assertPrice(
                new OrderDraft(9_000, CustomerTier.VIP, true, "SAVE10", DeliveryMethod.EXPRESS),
                new PriceBreakdown(9_000, 2_700, 6_300, 1_500, 7_800)
        );
    }

    @Test
    void exactlyTenThousandNetCentsGetsFreeShipping() {
        assertPrice(
                new OrderDraft(10_000, CustomerTier.BASIC, false, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(10_000, 0, 10_000, 0, 10_000)
        );
    }

    @Test
    void oneCentBelowTheThresholdStillPaysShipping() {
        assertPrice(
                new OrderDraft(9_999, CustomerTier.BASIC, false, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(9_999, 0, 9_999, 700, 10_699)
        );
    }

    @Test
    void oneCentIsAValidSubtotal() {
        assertPrice(
                new OrderDraft(1, CustomerTier.BASIC, false, null, DeliveryMethod.STANDARD),
                new PriceBreakdown(1, 0, 1, 700, 701)
        );
    }

    @Test
    void zeroIsNotAValidSubtotal() {
        OrderDraft draft = new OrderDraft(
                0,
                CustomerTier.BASIC,
                false,
                null,
                DeliveryMethod.STANDARD
        );

        assertThrows(IllegalArgumentException.class, () -> policy.calculate(draft));
    }

    private void assertPrice(OrderDraft draft, PriceBreakdown expected) {
        assertEquals(expected, policy.calculate(draft));
    }
}
