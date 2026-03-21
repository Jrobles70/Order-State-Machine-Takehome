# Order State Machine

A FastAPI service that models an order state machine with stage-dependent failure recovery, built for a ticket marketplace checkout flow.

## What I Built and Why

This service enforces a strict order lifecycle: creation → payment authorization → capture → fulfillment. Each stage can fail, and recovery depends on *where* the failure happens:

- **Payment decline** → reject the order. No cleanup needed.
- **Capture failure** → void the authorization, cancel the order.
- **Void also fails** → escalate to `needs_attention` for manual resolution.
- **Fulfillment failure** → escalate to `needs_attention` (money captured but tickets not delivered).

The core is a **transition table with embedded recovery**: a declarative structure that defines every valid state change and what to do when things go wrong. The orchestrator walks this table, accumulating errors during recovery chains and only recording a history entry when the order's state actually changes.

### State Machine

```
initialized → payment_authorized → captured → complete
                                 ↘ cancelled (void after capture failure)
                                 ↘ needs_attention (void fails, or fulfillment fails)
           ↘ rejected (payment declined)
```

## How to Run

### Prerequisites
- Python 3.12+

### Setup
```bash
make setup
```

### Start the Server
```bash
make run
```

Once the server is running, I recommend using the interactive API docs at http://localhost:8000/docs to explore and test the endpoints.

### Run Tests
```bash
make test
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orders` | Create an order (`{"event_id": "...", "quantity": 2, "section": "A", "row": "1", "amount_cents": 9999, "currency": "USD"}`) |
| POST | `/orders/{id}/authorize` | Authorize payment (`{"card_number": "4242...", "exp_month": 12, "exp_year": 2027, "cvv": "123"}`) |
| POST | `/orders/{id}/complete` | Capture + fulfill (with automatic recovery) |
| GET | `/orders/{id}` | Get order state and full history |

### Test Cards

| Card Number | Behavior |
|-------------|----------|
| `4242424242424242` | All operations succeed |
| `4000000000000002` | Authorization declined |
| `4000000000000341` | Capture fails, void succeeds → cancelled |
| `4000000000009995` | Capture fails, void fails → needs_attention |
| `4000000000000259` | Fulfillment fails → needs_attention |

## Tradeoffs

- **In-memory storage** — orders are lost on restart. Acceptable for a prototype; a real system would use a database with the repository pattern.
- **Synchronous payment calls** — fine for a stub, but a real provider would need async with timeouts.
- **Fulfillment simulated via card number** — in production, fulfillment would be a separate service/interface. Here it's controlled by the same card-based stub for simplicity.
- **Single-process state** — no concurrency protection. A real system would need optimistic locking or similar.

## What I'd Do Differently With More Time

- **Persistent storage** with PostgreSQL and a repository pattern for easy swap
- **Richer history metadata** — card last four digits, authorization IDs, provider error codes on each history entry
- **Separate payment attempt model** — move authorization/capture/void identifiers and attempt metadata off the `Order` model into a dedicated payment-attempts record
- **Idempotency keys** on action endpoints to prevent duplicate processing
- **Webhook/callback support** for `needs_attention` orders to alert operations teams
- **Separate fulfillment interface** — a proper `FulfillmentProvider` abstraction rather than card-based simulation
- **Richer order pricing** — taxes, per-ticket pricing breakdowns, and discount/promo code support
- **State history** - Add Dashboard or endpoint to properly display state history for easy debugging
