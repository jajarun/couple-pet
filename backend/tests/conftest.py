import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register tables on Base.metadata
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # push_service / push_scheduler 各自开 SessionLocal 发推、扫库（不走请求作用域），
    # 测试里把它们指到同一个内存库，否则会连到 dev.db 看不到测试数据。
    monkeypatch.setattr("app.push_service.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.push_scheduler.SessionLocal", TestingSessionLocal)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.session_factory = TestingSessionLocal  # 让测试能开同库会话查数据
        yield c
    app.dependency_overrides.clear()


def register(client, nickname="alice", password="pw123456"):
    return client.post("/auth/register", json={"nickname": nickname, "password": password})


def auth_headers(client, nickname="alice", password="pw123456"):
    r = register(client, nickname, password)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
