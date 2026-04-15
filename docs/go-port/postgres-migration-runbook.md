# Postgres Migration Runbook (Phase 0)

SQLite is allowed for local development only.
Production cutover to marketd requires PostgreSQL.

## 1. Provision PostgreSQL
- Create managed Postgres instance.
- Capture full `DATABASE_URL`.

## 2. Point Django to PostgreSQL
- Set `DATABASE_URL` in backend environment.
- Run:

```bash
cd backend
python manage.py migrate
```

## 3. Data migration (if starting from SQLite)
- Export and load data using Django serializers or DB-native tooling.
- Validate row counts for `accounts_user`, `api_trade`, `api_transaction`.

## 4. Enable marketd shadow
- Deploy marketd with:
  - `USE_GO_MARKETD=false`
  - `MARKETD_SHADOW_MODE=true`

## 5. Cutover gate
- Confirm at least 7 days of shadow parity before enabling writes.
