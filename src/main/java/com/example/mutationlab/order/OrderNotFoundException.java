package com.example.mutationlab.order;

public class OrderNotFoundException extends RuntimeException {

    public OrderNotFoundException(long id) {
        super("Purchase order " + id + " was not found");
    }
}
