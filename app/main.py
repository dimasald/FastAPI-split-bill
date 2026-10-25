from fastapi import FastAPI
from app.database import engine, Base
from app.routers import auth
from app.routers import groups

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Split Bill API")

app.include_router(auth.router)
app.include_router(groups.router)

app.get("/")
def read_root():
    return {"message": "Welcome to Split bill API. open /docs for test."}
