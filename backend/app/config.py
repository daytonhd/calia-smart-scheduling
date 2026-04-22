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
