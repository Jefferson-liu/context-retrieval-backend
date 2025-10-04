import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.ai.embedding import Embedder


async def main() -> None:
    embedder = Embedder()
    vec = await embedder.generate_embedding("Vector coffee roasters")
    print(len(vec))


if __name__ == "__main__":
    asyncio.run(main())
