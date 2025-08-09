from __future__ import annotations
import asyncio
from api.app import FastAPIManager


server_manager = FastAPIManager()

if __name__ == "__main__":
    asyncio.run(server_manager.start_server())