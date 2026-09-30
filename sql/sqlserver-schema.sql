CREATE TABLE purchase_orders (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    subtotal_cents BIGINT NOT NULL,
    customer_tier VARCHAR(20) NOT NULL,
    first_purchase BIT NOT NULL,
    coupon_code VARCHAR(32) NULL,
    delivery_method VARCHAR(20) NOT NULL,
    discount_cents BIGINT NOT NULL,
    net_cents BIGINT NOT NULL,
    shipping_cents BIGINT NOT NULL,
    total_cents BIGINT NOT NULL,
    created_at DATETIME2(6) NOT NULL,
    CONSTRAINT ck_purchase_orders_subtotal_positive CHECK (subtotal_cents > 0),
    CONSTRAINT ck_purchase_orders_discount_nonnegative CHECK (discount_cents >= 0),
    CONSTRAINT ck_purchase_orders_shipping_nonnegative CHECK (shipping_cents >= 0),
    CONSTRAINT ck_purchase_orders_total_nonnegative CHECK (total_cents >= 0)
);
