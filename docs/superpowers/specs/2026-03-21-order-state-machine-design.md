# Order State Machine — Design Spec

## Overview

A small FastAPI service that models an order state machine with stage-dependent failure recovery for a ticket marketplace checkout flow. Orders move through states from creation to completion, with automatic recovery when things go wrong at different stages.

## States

```
initialized → payment_authorized → captured → complete
                                 ↘ cancelled (via auto-void after capture failure)
                                 ↘ needs_attention (capture fails + void fails, OR fulfillment fails after capture)
           ↘ rejected (payment declined)
```

**Enum values:** `initialized`, `payment_authorized`, `captured`, `complete`, `cancelled`, `rejected`, `needs_attention`

## Transition Table

| From                  | Action    | On Success           | On Failure                                          |
|-----------------------|-----------|----------------------|-----------------------------------------------------|
| `initialized`         | `authorize` | `payment_authorized` | `rejected`                                         |
| `payment_authorized`  | `capture`   | `captured`           | attempt void → `cancelled` or `needs_attention`    |
| `captured`            | `fulfill`   | `complete`           | `needs_attention`                                  |

Any other `(state, action)` pair is invalid.

The user-facing `POST /orders/{id}/complete` endpoint orchestrates `capture` → `fulfill` as a single request. Internally, the orchestrator walks the transition table: capture the payment, then fulfill. If capture fails, void is attempted as recovery. If fulfillment fails after capture, the order goes to `needs_attention` (money taken, tickets not delivered — requires manual resolution).

## State History

Every order maintains an append-only history list. A history entry is written **only when the order's state actually changes**. Each entry records:

- `from_state` — the order's state before the transition
- `to_state` — the state the order moved to
- `trigger` — what initiated the transition (e.g., `authorize`, `complete`, `auto_void`, `auto_escalation`)
- `errors` — a list of `{action, message}` pairs representing failures that occurred during or leading to this transition. Empty list when nothing went wrong. Accumulates as recovery steps fail.
- `timestamp` — when the transition occurred

**Rules:**
- Only write a history entry when `current_state` actually changes. Errors accumulate in memory during the recovery chain and get attached to whatever transition finally lands.
- Validation errors (e.g., wrong state for the requested action) return API errors and do not create history entries.
- The history log is never mutated or truncated. It is the source of truth for debugging.

### Examples

**Happy path** — 3 entries:
```
1. initialized → payment_authorized | trigger: authorize | errors: []
2. payment_authorized → captured    | trigger: complete  | errors: []
3. captured → complete              | trigger: complete  | errors: []
```

**Payment decline** — 1 entry:
```
1. initialized → rejected | trigger: authorize | errors: [{action: "authorize", message: "card declined"}]
```

**Capture fails, void succeeds** — 2 entries:
```
1. initialized → payment_authorized | trigger: authorize | errors: []
2. payment_authorized → cancelled   | trigger: auto_void | errors: [{action: "capture", message: "capture failed"}]
```

**Capture fails, void also fails** — 2 entries:
```
1. initialized → payment_authorized | trigger: authorize       | errors: []
2. payment_authorized → needs_attention | trigger: auto_escalation | errors: [{action: "capture", message: "capture failed"}, {action: "void", message: "void failed"}]
```

**Capture succeeds, fulfillment fails** — 3 entries:
```
1. initialized → payment_authorized | trigger: authorize       | errors: []
2. payment_authorized → captured    | trigger: complete        | errors: []
3. captured → needs_attention       | trigger: auto_escalation | errors: [{action: "fulfill", message: "fulfillment failed"}]
```

## Order Model

An order stores:
- `id` — unique identifier
- `current_state` — current state enum value
- `card_number` — the card used for payment (set at authorize time)
- `amount` — order amount (set at creation time)
- `authorization_id` — payment authorization ID (set after successful authorize, used by capture/void)
- `created_at` — timestamp of creation
- `history` — append-only list of history entries

## Payment Interface

```python
class PaymentProvider:
    def authorize(card_number: str, amount: float) -> PaymentResult
    def capture(authorization_id: str) -> PaymentResult
    def void(authorization_id: str) -> PaymentResult
```

`PaymentResult` contains `success: bool`, `authorization_id: str | None`, and `error: str`.

### Stub Implementation — Card-Based Outcomes

Default behavior is success. Specific card numbers trigger specific failure modes:

| Card Number          | Behavior                              |
|----------------------|---------------------------------------|
| `4000000000000002`   | Authorization fails (decline)         |
| `4000000000000341`   | Capture fails, void succeeds          |
| `4000000000009995`   | Capture fails, void also fails        |
| `4000000000000259`   | Fulfillment fails (after successful capture) |
| Any other card       | All operations succeed                |

## API Endpoints

```
POST   /orders                  # Create a new order (amount in request body, returns order in "initialized" state)
POST   /orders/{id}/authorize   # Authorize payment (card_number in request body, stores authorization_id on order)
POST   /orders/{id}/complete    # Complete order: capture + fulfill (triggers recovery on failure)
GET    /orders/{id}             # Get order current state + full history
```

- `POST /orders` accepts `amount` in the request body
- `POST /orders/{id}/authorize` accepts `card_number` in the request body. The order's stored `amount` is passed to the payment provider. On success, the returned `authorization_id` is stored on the order for use by capture/void.
- The `complete` endpoint orchestrates capture → fulfill as a single request, with automatic recovery. The orchestrator checks the card number to determine if fulfillment should be simulated as a failure.
- Void is an internal recovery action, not a user-facing endpoint
- Invalid state transitions return 400 errors with no history entry

## Project Structure

```
app/
├── main.py                        # FastAPI app, startup, routes
├── models.py                      # Order model, state enum, history entry, payment models
├── state_machine.py               # Transition table, enforcement
├── orchestrator.py                # Coordinates payment, state machine, history, recovery chain
├── payment.py                     # Payment interface + stub implementation
├── store.py                       # In-memory order storage (dict wrapper)
tests/
├── test_state_machine.py          # Unit tests for transition logic
├── test_orchestrator.py           # Service-level tests (all failure scenarios)
├── test_payment.py                # Payment stub behavior
├── test_api.py                    # Integration tests against FastAPI endpoints
└── conftest.py                    # Shared fixtures (store clearing, test client)
```

- **State machine** — pure logic, no I/O. Enforces valid transitions. Returns the success state and failure state/recovery action for a given `(state, action)` pair.
- **Orchestrator** — coordinates payment calls, state transitions, history recording, and drives the recovery chain. The orchestrator queries the state machine for what to do, then executes it.
- **Routes** — live in `main.py` since they're thin (validate input, delegate to orchestrator, return responses).
- **Store** — module-level dict singleton, persists for process lifetime, cleared between tests via pytest fixture.

If during implementation the state machine and orchestrator turn out to be trivially small, they can be merged into one module. Let the logic dictate the boundaries, not the folder structure.

## Testing

Required scenarios per the challenge:

1. **Happy path** — create → authorize → complete → order is `complete`
2. **Payment decline** — authorize with decline card → order is `rejected`
3. **Capture failure, void succeeds** — authorize succeeds, capture fails, auto-void succeeds → order is `cancelled`
4. **Capture failure, void fails** — authorize succeeds, capture fails, auto-void fails → order is `needs_attention`

Additional scenario from our design:

5. **Fulfillment failure** — authorize succeeds, capture succeeds, fulfillment fails → order is `needs_attention`

Tests are colocated with their modules. Route-level tests use FastAPI's `TestClient`. A shared `autouse` fixture clears the in-memory store between tests.

## README Notes — Future Improvements

- Enrich history metadata with contextual data (card last four digits, authorization IDs, provider error codes)
- Persistent storage (PostgreSQL) with the repository pattern
- Async payment calls with timeout handling
- Webhook/callback support for `needs_attention` orders
- Idempotency keys on action endpoints
