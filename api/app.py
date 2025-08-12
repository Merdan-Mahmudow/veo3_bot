from fastapi import FastAPI
import uvicorn
from api.routers.system import routes as SystemRoutes
from api.routers.generate import routes as GenerateRoutes
from api.routers.auth import routes as AuthRoutes

class FastAPIManager:
    def __init__(self):
        self.api = FastAPI()
        self.add_routers()

    def add_routers(self):
        self.api.include_router(SystemRoutes.router)
        self.api.include_router(GenerateRoutes.router)
        self.api.include_router(GenerateRoutes.public_router)
        self.api.include_router(AuthRoutes.router)

    def start_server(self):
        uvicorn.run(self.api, host="0.0.0.0", port=8000)