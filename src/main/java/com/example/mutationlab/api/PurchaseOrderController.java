package com.example.mutationlab.api;

import com.example.mutationlab.order.PurchaseOrderDetails;
import com.example.mutationlab.order.PurchaseOrderService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;

@RestController
@RequestMapping("/api/orders")
public class PurchaseOrderController {

    private final PurchaseOrderService service;

    public PurchaseOrderController(PurchaseOrderService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<OrderResponse> create(@Valid @RequestBody CreateOrderRequest request) {
        PurchaseOrderDetails created = service.create(request.toCommand());
        return ResponseEntity
                .created(URI.create("/api/orders/" + created.id()))
                .body(OrderResponse.from(created));
    }

    @GetMapping("/{id}")
    public OrderResponse findById(@PathVariable long id) {
        return OrderResponse.from(service.findById(id));
    }
}
