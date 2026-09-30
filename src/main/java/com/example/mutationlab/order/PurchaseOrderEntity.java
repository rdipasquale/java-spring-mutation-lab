package com.example.mutationlab.order;

import com.example.mutationlab.domain.CustomerTier;
import com.example.mutationlab.domain.DeliveryMethod;
import com.example.mutationlab.pricing.OrderDraft;
import com.example.mutationlab.pricing.PriceBreakdown;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "purchase_orders")
public class PurchaseOrderEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "subtotal_cents", nullable = false)
    private long subtotalCents;

    @Enumerated(EnumType.STRING)
    @Column(name = "customer_tier", nullable = false, length = 20)
    private CustomerTier customerTier;

    @Column(name = "first_purchase", nullable = false)
    private boolean firstPurchase;

    @Column(name = "coupon_code", length = 32)
    private String couponCode;

    @Enumerated(EnumType.STRING)
    @Column(name = "delivery_method", nullable = false, length = 20)
    private DeliveryMethod deliveryMethod;

    @Column(name = "discount_cents", nullable = false)
    private long discountCents;

    @Column(name = "net_cents", nullable = false)
    private long netCents;

    @Column(name = "shipping_cents", nullable = false)
    private long shippingCents;

    @Column(name = "total_cents", nullable = false)
    private long totalCents;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected PurchaseOrderEntity() {
        // Required by JPA.
    }

    private PurchaseOrderEntity(
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
        this.subtotalCents = subtotalCents;
        this.customerTier = customerTier;
        this.firstPurchase = firstPurchase;
        this.couponCode = couponCode;
        this.deliveryMethod = deliveryMethod;
        this.discountCents = discountCents;
        this.netCents = netCents;
        this.shippingCents = shippingCents;
        this.totalCents = totalCents;
        this.createdAt = createdAt;
    }

    public static PurchaseOrderEntity from(OrderDraft draft, PriceBreakdown price, Instant createdAt) {
        return new PurchaseOrderEntity(
                draft.subtotalCents(),
                draft.customerTier(),
                draft.firstPurchase(),
                draft.couponCode(),
                draft.deliveryMethod(),
                price.discountCents(),
                price.netCents(),
                price.shippingCents(),
                price.totalCents(),
                createdAt
        );
    }

    PurchaseOrderDetails toDetails() {
        return new PurchaseOrderDetails(
                id,
                subtotalCents,
                customerTier,
                firstPurchase,
                couponCode,
                deliveryMethod,
                discountCents,
                netCents,
                shippingCents,
                totalCents,
                createdAt
        );
    }

    public Long getId() {
        return id;
    }

    public long getSubtotalCents() {
        return subtotalCents;
    }

    public CustomerTier getCustomerTier() {
        return customerTier;
    }

    public boolean isFirstPurchase() {
        return firstPurchase;
    }

    public String getCouponCode() {
        return couponCode;
    }

    public DeliveryMethod getDeliveryMethod() {
        return deliveryMethod;
    }

    public long getDiscountCents() {
        return discountCents;
    }

    public long getNetCents() {
        return netCents;
    }

    public long getShippingCents() {
        return shippingCents;
    }

    public long getTotalCents() {
        return totalCents;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
