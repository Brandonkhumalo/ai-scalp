# marketd Ownership Contract

## Purpose
Define clear write ownership between Django and marketd to prevent dual-writer conflicts.

## Phase 0 and 1 (Shadow)
- `USE_GO_MARKETD=false`
- `MARKETD_SHADOW_MODE=true`
- Django remains source of writes for scalping closes and reconciliation updates.
- marketd only logs `would_close`, `would_mark_closed`, `would_delete_duplicate` actions.

## Phase 3 (Cutover)
- `USE_GO_MARKETD=true`
- `MARKETD_SHADOW_MODE=false`
- Disable Django cron/management commands that perform:
  - scalping auto-close writes
  - position reconciliation writes
- marketd becomes exclusive writer for those workflows.

## Shared tables (Django schema owner)
- `accounts_user` (read-only in marketd)
- `api_trade` (read/write in marketd for scoped workflows)
- `api_transaction` (write trade P&L transactions in marketd)

## Invariants
- Money values stay decimal, never float in persisted writes.
- Close-path source of truth is broker verification; DB update only after broker-close verification.
- Keep Python implementation in-repo for one release cycle post-cutover for rollback.
