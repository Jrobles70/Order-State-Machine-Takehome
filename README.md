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
pip install -e ".[dev]"
```

### Start the Server
```bash
uvicorn app.main:app --reload
```

API docs available at http://localhost:8000/docs

### Run Tests
```bash
pytest -v
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orders` | Create an order (`{"amount": 99.99}`) |
| POST | `/orders/{id}/authorize` | Authorize payment (`{"card_number": "4242..."}`) |
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
- **Async payment calls** with configurable timeouts
- **Idempotency keys** on action endpoints to prevent duplicate processing
- **Webhook/callback support** for `needs_attention` orders to alert operations teams
- **Separate fulfillment interface** — a proper `FulfillmentProvider` abstraction rather than card-based simulation
