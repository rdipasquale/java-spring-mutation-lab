package com.example.mutationlab.order;

import com.example.mutationlab.pricing.OrderDraft;
import com.example.mutationlab.pricing.PriceBreakdown;
import com.example.mutationlab.pricing.PricingPolicy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Service
public class PurchaseOrderService {

    private final PricingPolicy pricingPolicy;
    private final PurchaseOrderRepository repository;

    public PurchaseOrderService(PricingPolicy pricingPolicy, PurchaseOrderRepository repository) {
        this.pricingPolicy = pricingPolicy;
        this.repository = repository;
    }

    @Transactional
    public PurchaseOrderDetails create(CreatePurchaseOrderCommand command) {
        OrderDraft draft = new OrderDraft(
                command.subtotalCents(),
                command.customerTier(),
                command.firstPurchase(),
                command.couponCode(),
                command.deliveryMethod()
        );

        PriceBreakdown price = pricingPolicy.calculate(draft);
        PurchaseOrderEntity entity = PurchaseOrderEntity.from(draft, price, Instant.now());

        return repository.save(entity).toDetails();
    }

    @Transactional(readOnly = true)
    public PurchaseOrderDetails findById(long id) {
        return repository.findById(id)
                .orElseThrow(() -> new OrderNotFoundException(id))
                .toDetails();
    }
}
