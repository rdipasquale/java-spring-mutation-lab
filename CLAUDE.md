# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests (H2 in-memory, MODE=MSSQLServer)
mvn clean test

# Run a single test class
mvn clean test -Dtest=PricingPolicyTest

# Run tests + generate JaCoCo coverage report (target/site/jacoco/index.html)
mvn clean verify

# Run PIT mutation testing (target/pit-reports/index.html)
mvn clean test-compile org.pitest:pitest-maven:mutationCoverage

# Run tests + PIT with the full solution test suite
mvn -Psolution-tests clean test
mvn -Psolution-tests clean test-compile org.pitest:pitest-maven:mutationCoverage

# Run the app locally (H2, profile=local)
mvn spring-boot:run
```

The app runs on `http://localhost:8080`. H2 console at `/h2-console` (URL: `jdbc:h2:mem:mutationlab;MODE=MSSQLServer;DATABASE_TO_UPPER=false;DB_CLOSE_DELAY=-1`, user: `sa`, no password).

## Architecture

The sole mutation target is `PricingPolicy` — all JaCoCo and PIT configuration is scoped to that class. Everything else (controller, service, repository) exists to make it a realistic Spring Boot project.

```
api/        — REST layer: PurchaseOrderController, CreateOrderRequest, OrderResponse, RestExceptionHandler
order/      — PurchaseOrderService, PurchaseOrderEntity, PurchaseOrderRepository (Spring Data JPA)
pricing/    — PricingPolicy (mutation target), OrderDraft (input record), PriceBreakdown (output record)
domain/     — CustomerTier enum (BASIC, PREMIUM, VIP), DeliveryMethod enum (STANDARD, EXPRESS, PICKUP)
config/     — PricingConfiguration (Spring @ConfigurationProperties)
```

**PricingPolicy rules** (the exact numbers PIT will mutate):
- PREMIUM → 10 % discount; VIP → 15 %; first purchase adds 5 pp.
- Coupon `SAVE10` (case-insensitive) subtracts 1 000 cents.
- Total discount capped at 30 % of subtotal.
- `PICKUP` is always free; net ≥ 10 000 cents → free shipping; otherwise STANDARD = 700 cents, EXPRESS = 1 500 cents.

**Test layout:**
- `src/test/java/.../pricing/PricingPolicyTest.java` — the intentionally weak suite (checks invariants, not exact values). This is what participants improve.
- `src/solution-test/java/.../pricing/PricingPolicySpecificationTest.java` — the reference suite (exact `assertEquals` on every field of `PriceBreakdown`). Only compiled with `-Psolution-tests`.
- `src/test/java/.../order/` and `.../api/` — service, repository (H2), and controller slice tests (not mutated).

**Database profiles:**
- `local` / `test`: H2 in-memory with `MODE=MSSQLServer`.
- `prod`: SQL Server via env vars `DB_URL`, `DB_USERNAME`, `DB_PASSWORD`; `ddl-auto: validate` (schema must exist; see `sql/sqlserver-schema.sql`).

## Skills

Two project skills are available (defined in `.claude/skills/`):
- `/salud-de-suite` — verifies suite health (flakiness, baseline time) before mutation testing.
- `/caza-de-mutantes` — runs PIT, normalizes results, and triages survivors. **Always run `/salud-de-suite` first.**

`.github/skills/` holds generated GitHub Copilot copies of these skills (script/reference paths rewritten to be repo-root-relative). Never edit them by hand: after changing `.claude/skills/`, run `python3 tools/install_copilot_skills.py` (`--check` fails if they drifted; `--user` installs to `~/.copilot/skills`).

Example requests are in `examples/requests.http`.
