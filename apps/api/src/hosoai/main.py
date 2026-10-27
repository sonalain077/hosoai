from fastapi import FastAPI

app = FastAPI(title="Hồ Sơ AI")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
