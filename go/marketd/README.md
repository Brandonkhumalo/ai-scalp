# marketd

Go service for low-latency market loops extracted from Django:
- market-hours checks
- scalping target loop
- position reconciliation loop
- Alpaca API client with shared rate limiting

## Run in Shadow Mode

```bash
cd go/marketd
cp .env.example .env
set -a; source .env; set +a
make run-shadow
```

`MARKETD_SHADOW_MODE=true` means marketd only logs what it would do.
Django remains the writer until cutover.

## Build

```bash
cd go/marketd
make build
```

## Health endpoint

- `GET /healthz` on `MARKETD_LISTEN_ADDR` (default `:8090`)

## Integration contract

- Django owns schema migrations and admin.
- marketd reads/writes `api_trade`, `api_transaction`, `accounts_user`.
- During shadow mode, marketd writes nothing.
- At cutover, disable Django scalping/reconciliation management loops before enabling marketd writes.
