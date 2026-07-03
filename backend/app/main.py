from fastapi import FastAPI

from app.routers import actions, auth, avatars, couples, events

app = FastAPI(title="AI Couple Pet Game API")

app.include_router(auth.router)
app.include_router(couples.router)
app.include_router(avatars.router)
app.include_router(actions.router)
app.include_router(events.router)


@app.get("/health")
def health():
    return {"status": "ok"}
