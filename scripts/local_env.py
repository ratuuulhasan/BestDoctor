"""Create local development secrets once, without printing them."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
try:
    with target.open("x", encoding="utf-8") as stream:
        stream.write(
            f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\n"
            f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
            "POSTGRES_DB=best_doctor\nPOSTGRES_USER=best_doctor\n"
            "POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=55432\nDJANGO_DEBUG=1\n"
        )
except FileExistsError:
    print("Using the existing .env file.")
