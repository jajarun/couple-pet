from fastapi import FastAPI

app = FastAPI(title="AI Pet Game API")


@app.get("/health")
def health():
    return {"status": "ok"}
