package com.example.mutationlab.order;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import com.example.mutationlab.pricing.OrderDraft;
import com.example.mutationlab.pricing.PriceBreakdown;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@DataJpaTest
@ActiveProfiles("test")
class PurchaseOrderRepositoryTest {

    @Autowired
    private PurchaseOrderRepository repository;

    @Test
    void storesAndLoadsAnOrderUsingH2() {
        OrderDraft draft = new OrderDraft(
                5_000,
                CustomerTier.BASIC,
                false,
                null,
                DeliveryMethod.STANDARD
        );
        PriceBreakdown price = new PriceBreakdown(5_000, 0, 5_000, 700, 5_700);
        Instant createdAt = Instant.parse("2026-01-01T00:00:00Z");

        PurchaseOrderEntity saved = repository.saveAndFlush(
                PurchaseOrderEntity.from(draft, price, createdAt)
        );
        PurchaseOrderEntity loaded = repository.findById(saved.getId()).orElseThrow();

        assertAll(
                () -> assertNotNull(loaded.getId()),
                () -> assertEquals(CustomerTier.BASIC, loaded.getCustomerTier()),
                () -> assertEquals(DeliveryMethod.STANDARD, loaded.getDeliveryMethod()),
                () -> assertEquals(5_700, loaded.getTotalCents()),
                () -> assertEquals(createdAt, loaded.getCreatedAt())
        );
    }
}
