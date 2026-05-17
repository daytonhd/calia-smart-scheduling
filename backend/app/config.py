import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/scheduling",
)


# Comma-separated list of allowed origins for CORS. MVP default targets the
# local Next.js dev server on both localhost and 127.0.0.1.
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _parse_origins(raw: str) -> List[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


CORS_ORIGINS: List[str] = _parse_origins(
    os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
)


# JWT auth config. JWT_SECRET_KEY MUST be set via environment variable in
# production — the default below is only for local development.
JWT_SECRET_KEY: str = os.getenv(
    "JWT_SECRET_KEY",
    "dev-only-insecure-secret-change-me",
)
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)
