# Order State Machine

A FastAPI service that models an order state machine with stage-dependent failure recovery, built for a ticket marketplace checkout flow.

## What I Built and Why

This service enforces a strict order lifecycle: creation → payment authorization → capture → fulfillment. Each stage can fail, and recovery depends on *where* the failure happens:

- **Payment decline** → reject the order. No cleanup needed.
- **Capture failure** → void the authorization, cancel the order.
- **Void also fails** → escalate to `needs_attention` for manual resolution.
- **Fulfillment failure** → escalate to `needs_attention` (money captured but tickets not delivered).

The core is a **transition table with embedded recovery**: a declarative structure that defines every valid state change and what to do when things go wrong. The orchestrator walks this table, accumulating errors during recovery chains and only recording a history entry when the order's state actually changes.

**PII-conscious storage** — The order model only retains the card's last four digits and expiration date. The full card number and CVV are used for the authorization call and then discarded — they never persist in memory or appear in order history.

**Input validation at the boundary** — Card numbers are validated for digit length (13–19), CVV for format (3–4 digits), and expiration dates are checked against the current month so expired cards are rejected before reaching the payment provider.

**Single `/complete` endpoint for capture + fulfillment** — Rather than exposing separate capture and fulfill endpoints, the client calls one endpoint and the service orchestrates the multi-step process. This keeps failure-recovery logic server-side where it belongs — the client doesn't need to know that a failed capture should trigger a void attempt.

**Error accumulation across recovery chains** — When a recovery sequence fires (e.g., capture fails → void attempted → void fails), all errors are collected into a single history entry. You get a complete picture of what happened without stitching together multiple records.

**Test cards modeled after Stripe** — Card numbers drive failure scenarios through the full stack. No mocks or feature flags needed — the same code paths that run in tests are the ones that run in production.

**Amount in cents with explicit currency** — Money is stored as integer cents with a currency enum, avoiding floating-point precision issues.

### State Machine

```
initialized → payment_authorized → captured → complete
                                 ↘ cancelled (void after capture failure)
                                 ↘ needs_attention (void fails, or fulfillment fails)
           ↘ rejected (payment declined)
```

## How to Run

### Prerequisites
- Python 3.12+ installed and available on your `PATH` as `python3.12`

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
- **`/complete` couples capture and fulfillment** — a deliberate simplification, but it means you can't capture payment and delay fulfillment (e.g., for held orders or manual review before ticket delivery).
- **No partial failure rollback on fulfillment** — once payment is captured, a fulfillment failure escalates to `needs_attention` but doesn't attempt a refund automatically.

## What I'd Do Differently With More Time

- **Persistent storage** with PostgreSQL and a repository pattern for easy swap
- **Richer history metadata** — card last four digits, authorization IDs, provider error codes on each history entry
- **Separate payment attempt model** — move authorization/capture/void identifiers and attempt metadata off the `Order` model into a dedicated payment-attempts record
- **Idempotency keys** on action endpoints to prevent duplicate processing
- **Webhook/callback support** for `needs_attention` orders to alert operations teams
- **Separate fulfillment interface** — a proper `FulfillmentProvider` abstraction rather than card-based simulation
- **Richer order pricing** — taxes, per-ticket pricing breakdowns, and discount/promo code support
- **Authentication/authorization** — scope order actions to the authenticated user rather than allowing any caller to operate on any order
- **User-friendly error responses** — structured error codes and human-readable messages so clients can display actionable feedback (e.g., "Card declined — try a different payment method")
- **State history** - Add Dashboard or endpoint to properly display state history for easy debugging

## AI Usage

This project was built with [Claude Code](https://claude.com/claude-code). I used AI-assisted brainstorming to explore requirements, edge cases, and design tradeoffs before writing any code, then produced a detailed implementation plan. From there, the plan was executed in small iterative steps using test-driven development — writing failing tests first, implementing just enough to pass, then refining. Every step was reviewed and validated before moving on.
