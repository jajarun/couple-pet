from fastapi import FastAPI

from app.routers import auth, couples

app = FastAPI(title="AI Couple Pet Game API")

app.include_router(auth.router)
app.include_router(couples.router)


@app.get("/health")
def health():
    return {"status": "ok"}
