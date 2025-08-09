from fastapi import FastAPI
import uvicorn
from api.routers.system import routes

class FastAPIManager:
    def __init__(self):
        self.api = FastAPI()
        self.add_routers()

    def add_routers(self):
        self.api.include_router(routes.router)

    def start_server(self):
        uvicorn.run(self.api, host="0.0.0.0", port=8000)