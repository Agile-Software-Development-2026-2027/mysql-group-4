"""Isolated configuration, loaded before application imports in unit tests."""
import os

# Never use local database or mail credentials for the unit test process.
# Mail placeholders only allow importing Mission authentication dependencies;
# these tests do not call the mail service or send email.
os.environ.update({
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "SECRET_KEY": "unit-tests-only-not-a-production-secret",
    "MAIL_USERNAME": "test",
    "MAIL_PASSWORD": "test",
    "MAIL_FROM": "test@example.com",
    "MAIL_PORT": "587",
    "MAIL_SERVER": "localhost",
    "MAIL_STARTTLS": "False",
    "MAIL_SSL_TLS": "False",
})

import pytest
from collections.abc import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base
from app.db.session import get_async_session
from main import app
#Database sqlite in memoria RAM che sparisce alla fine dei test
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

#Crea tutte le tabelle all'inizio dei test e le cancella alla fine
@pytest.fixture
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

#crea la sessione del database locale dei test
@pytest.fixture
async def db_session(prepare_database) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session

#chiama le API senza avviare il server
@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
