package com.example.mutationlab.order;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import com.example.mutationlab.pricing.OrderDraft;
import com.example.mutationlab.pricing.PricingPolicy;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PurchaseOrderServiceTest {

    @Mock
    private PurchaseOrderRepository repository;

    private PurchaseOrderService service;

    @BeforeEach
    void setUp() {
        service = new PurchaseOrderService(new PricingPolicy(), repository);
    }

    @Test
    void createsAndPersistsAnOrder() {
        when(repository.save(any(PurchaseOrderEntity.class))).thenAnswer(invocation -> {
            PurchaseOrderEntity entity = invocation.getArgument(0);
            ReflectionTestUtils.setField(entity, "id", 42L);
            return entity;
        });

        PurchaseOrderDetails result = service.create(new CreatePurchaseOrderCommand(
                12_000,
                CustomerTier.PREMIUM,
                true,
                "SAVE10",
                DeliveryMethod.STANDARD
        ));

        ArgumentCaptor<PurchaseOrderEntity> captor = ArgumentCaptor.forClass(PurchaseOrderEntity.class);
        verify(repository).save(captor.capture());
        PurchaseOrderEntity persisted = captor.getValue();

        assertAll(
                () -> assertEquals(42L, result.id().longValue()),
                () -> assertEquals(12_000, persisted.getSubtotalCents()),
                () -> assertEquals(CustomerTier.PREMIUM, persisted.getCustomerTier()),
                () -> assertTrue(persisted.getDiscountCents() > 0),
                () -> assertTrue(persisted.getTotalCents() > 0)
        );
    }

    @Test
    void findsAnExistingOrder() {
        PurchaseOrderEntity entity = sampleEntity();
        ReflectionTestUtils.setField(entity, "id", 7L);
        when(repository.findById(7L)).thenReturn(Optional.of(entity));

        PurchaseOrderDetails result = service.findById(7L);

        assertEquals(7L, result.id().longValue());
        assertEquals(5_700, result.totalCents());
    }

    @Test
    void failsWhenOrderDoesNotExist() {
        when(repository.findById(99L)).thenReturn(Optional.empty());

        assertThrows(OrderNotFoundException.class, () -> service.findById(99L));
    }

    private static PurchaseOrderEntity sampleEntity() {
        OrderDraft draft = new OrderDraft(
                5_000,
                CustomerTier.BASIC,
                false,
                null,
                DeliveryMethod.STANDARD
        );
        return PurchaseOrderEntity.from(
                draft,
                new PricingPolicy().calculate(draft),
                Instant.parse("2026-01-01T00:00:00Z")
        );
    }
}
