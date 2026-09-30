package com.example.mutationlab.config;

import com.example.mutationlab.pricing.PricingPolicy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class PricingConfiguration {

    @Bean
    PricingPolicy pricingPolicy() {
        return new PricingPolicy();
    }
}
