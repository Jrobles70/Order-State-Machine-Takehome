# Realistic Order Data Collection

## Overview

Expand the Order model and API request schemas to collect realistic order data (customer info and card details) while ensuring PII is handled correctly — sensitive card data is never stored or logged.

## Request Models

### CreateOrderRequest

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| amount | float | yes | Existing field, must be > 0 |
| first_name | str | yes | Non-empty after stripping whitespace |
| last_name | str | yes | Non-empty after stripping whitespace |
| email | Optional[EmailStr] | no | Validated as email format when provided (via Pydantic `EmailStr`) |

### AuthorizeRequest

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| card_number | str | yes | Digits only, 13-19 chars. No Luhn check (out of scope for demo) |
| exp_month | int | yes | 1-12 |
| exp_year | int | yes | 4-digit year. Combined month+year must not be in the past |
| cvv | str | yes | 3-4 digits |

## Order Model Changes

New fields added to the `Order` model:

| Field | Type | Default | Stored |
|-------|------|---------|--------|
| first_name | str | required | yes |
| last_name | str | required | yes |
| email | Optional[str] | None | yes |
| exp_month | Optional[int] | None | yes (after auth) |
| exp_year | Optional[int] | None | yes (after auth) |
| last4 | Optional[str] | None | yes (existing, after auth) |

**Never stored on Order:** `card_number` (full), `cvv`. These exist only on request models.

## Sensitive Data Flow

The CVV and full card number follow this lifecycle:

1. Client sends `card_number` and `cvv` in `AuthorizeRequest`
2. Route handler passes `card_number`, `exp_month`, `exp_year` to `Orchestrator.authorize()`
3. CVV is **discarded at the route handler** — it is not passed to the orchestrator or payment provider. The stub provider does not perform real card verification, so CVV serves only as a realistic input field.
4. Orchestrator passes `card_number` to `PaymentProvider.authorize()` (existing behavior)
5. On success, orchestrator stores only `last4`, `exp_month`, `exp_year` on the Order
6. Full `card_number` goes out of scope and is never persisted

## Flow Changes

### POST /orders

- Accepts `first_name`, `last_name`, `email` (optional), and `amount`
- Creates Order with customer info populated

### POST /orders/{id}/authorize

- Accepts `card_number`, `exp_month`, `exp_year`, `cvv`
- Passes `card_number`, `exp_month`, `exp_year` to orchestrator (CVV discarded here)
- On successful auth, orchestrator stores `last4`, `exp_month`, `exp_year` on the Order

### Orchestrator.authorize()

- Signature adds `exp_month: int` and `exp_year: int` parameters
- On success, stores these on the Order alongside `last4` (existing)

## Response Serialization

All Order fields appear in API responses. Since `card_number` and `cvv` are never on the Order model, there is no risk of leaking sensitive data through GET /orders/{id} or other endpoints that return the Order.

## PII Handling

- Card number and CVV only exist in request models — never serialized to storage or responses
- No logging of raw card data
- Order responses include `last4` but never the full card number
- First name, last name, email are stored as-is (low-sensitivity PII) but excluded from logging

## What Doesn't Change

- State machine transitions
- Payment provider interface (`authorize()` still takes `card_number` and `amount`)
- Store module (just stores a wider Order)
- History/transition logic
- `StubPaymentProvider.should_fail_fulfillment()` — unchanged

## Tests

- Update existing tests to pass new required fields (`first_name`, `last_name` for order creation; full card details for authorization)
- Verify `first_name`, `last_name`, `email` persist on the Order after creation
- Verify `exp_month`, `exp_year` persist on the Order after successful authorization
- Verify `cvv` and full `card_number` are never present as attributes on the Order model
- Input validation cases (all should return 422):
  - `card_number` with letters or wrong length
  - `exp_month` outside 1-12
  - `exp_year` in the past
  - `cvv` with wrong digit count
  - Empty `first_name` or `last_name`
  - Invalid email format when provided
