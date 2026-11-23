"""Root seed script invoking backend seed."""
import asyncio
from backend.scripts.seed_data import seed

if __name__ == "__main__":
    asyncio.run(seed())
