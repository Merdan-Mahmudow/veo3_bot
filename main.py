from __future__ import annotations
from api.app import FastAPIManager


server_manager = FastAPIManager()

if __name__ == "__main__":
    server_manager.start_server()