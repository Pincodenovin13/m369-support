# Environment Variables

See `.env.example` for all variables. Key ones:

## Database
- `DATABASE_URL`
- `TEST_DATABASE_URL`

## JWT
- `JWT_SECRET_KEY` — **change in production**
- `JWT_SUPER_ADMIN_SECRET_KEY` — **change in production**
- `JWT_ACCESS_TOKEN_MINUTES` (default: 10080 = 7 days)
- `JWT_REFRESH_TOKEN_DAYS` (default: 30)

## Argon2id
- `ARGON2_TIME_COST` (default: 3)
- `ARGON2_MEMORY_COST` (default: 65536)
- `ARGON2_PARALLELISM` (default: 2)

## Encryption
- `ENCRYPTION_KEY` — Fernet key for secrets at rest

## CORS / Cookies
- `FRONTEND_URL` (default: http://localhost:3000)
- `COOKIE_SECURE` (default: false — set true in production)

## Generate Secure Keys

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
