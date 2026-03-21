# Realistic Order Data Collection

## Overview

Expand the Order model and API request schemas to collect realistic order data (customer info and card details) while ensuring PII is handled correctly — sensitive card data is never stored or logged.

## Request Models

### CreateOrderRequest

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| amount | float | yes | Existing field |
| first_name | str | yes | New |
| last_name | str | yes | New |
| email | Optional[str] | no | Optional for demo purposes |

### AuthorizeRequest

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| card_number | str | yes | Digits only, 13-19 chars |
| exp_month | int | yes | 1-12 |
| exp_year | int | yes | 4-digit year, not in the past |
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

**Never stored on Order:** `card_number` (full), `cvv`. These exist only on request models and are passed to the payment provider then discarded.

## Flow Changes

### POST /orders

- Accepts `first_name`, `last_name`, `email` (optional), and `amount`
- Creates Order with customer info populated

### POST /orders/{id}/authorize

- Accepts `card_number`, `exp_month`, `exp_year`, `cvv`
- Passes `card_number` to orchestrator (existing behavior)
- On successful auth, stores `last4`, `exp_month`, `exp_year` on the Order
- `cvv` and full `card_number` are discarded after use

### Orchestrator.authorize()

- Signature adds `exp_month: int` and `exp_year: int` parameters
- On success, stores these on the Order alongside `last4` (existing)

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

## Tests

- Update existing tests to pass new required fields
- Verify customer info persists after order creation
- Verify `exp_month`, `exp_year` persist after successful auth
- Verify `cvv` and full `card_number` are never on the Order model
- Validate input validation (bad card length, invalid exp_month, etc.)
