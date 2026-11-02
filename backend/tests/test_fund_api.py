from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import EmploymentLevel
from app.core.exceptions import FundLockedError
from app.crud.fund_repository import FundRepository
from app.db.models import User
from app.security import current_active_user
from app.services.fund_service import FundService
from main import app
from tests.factories import make_mission


@pytest.fixture
async def teacher(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(), email="mario.rossi@example.com", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
        name="Mario", surname="Rossi", fiscal_code="RSSMRA80A01H501U",
        employment_level=EmploymentLevel.PROFESSORE_ORDINARIO, department="Informatica",
    )
    db_session.add(user)
    await db_session.commit()
    app.dependency_overrides[current_active_user] = lambda: user
    return user


async def test_fund_crud_flow(client: AsyncClient, teacher: User):
    created = await client.post("/api/v1/funds", json={
        "name": "Progetto PRIN", "description": "Fondi di ricerca", "amount": "15000.50",
    })
    assert created.status_code == 201
    body = created.json()
    assert body["responsibleFc"] == teacher.fiscal_code
    assert body["amount"] == "15000.50"
    fund_id = body["id"]

    listing = await client.get("/api/v1/funds")
    assert listing.status_code == 200
    assert [f["id"] for f in listing.json()["content"]] == [fund_id]

    updated = await client.put(f"/api/v1/funds/{fund_id}", json={"name": "PRIN 2026", "amount": "100"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "PRIN 2026"

    deleted = await client.delete(f"/api/v1/funds/{fund_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/funds/{fund_id}")).status_code == 404


async def test_create_fund_rejects_negative_amount(client: AsyncClient, teacher: User):
    response = await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "-5"})
    assert response.status_code == 422


async def test_funds_require_login(client: AsyncClient):
    assert (await client.get("/api/v1/funds")).status_code == 401


async def test_fund_managers_lists_only_users_with_a_fund(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    db_session.add(User(
        id=uuid4(), email="luigi.verdi@example.com", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
        name="Luigi", surname="Verdi", fiscal_code="VRDLGI85B02F205X",
        employment_level=EmploymentLevel.RICERCATORE, department="Fisica",
    ))
    await db_session.commit()
    await client.post("/api/v1/funds", json={"name": "Fondo A", "amount": "10"})
    await client.post("/api/v1/funds", json={"name": "Fondo B", "amount": "20"})

    response = await client.get("/api/v1/users/fund-managers")
    assert response.status_code == 200
    assert [u["fiscalCode"] for u in response.json()] == [teacher.fiscal_code]


async def _make_mission(db_session: AsyncSession, requester: User):
    mission = make_mission(requester_id=requester.id, fund_manager_id=requester.id)
    db_session.add(mission)
    await db_session.commit()
    return mission


async def test_fund_can_be_locked_by_one_mission_at_a_time(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = UUID((await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "100"})).json()["id"])
    first_id = (await _make_mission(db_session, teacher)).id
    second_id = (await _make_mission(db_session, teacher)).id
    service = FundService(db_session, FundRepository(db_session))

    locked = await service.lock_for_mission(fund_id, first_id)
    await db_session.commit()
    assert locked.locked_by_mission_id == first_id

    with pytest.raises(FundLockedError):
        await service.lock_for_mission(fund_id, second_id)

    available = await client.get("/api/v1/funds/available")
    assert available.json()["content"] == []
    assert (await client.delete(f"/api/v1/funds/{fund_id}")).status_code == 409
    # Nei test la sessione è condivisa con l'API: il 409 ha fatto rollback e scaduto gli oggetti.
    for obj in list(db_session.identity_map.values()):
        await db_session.refresh(obj)

    await service.release_from_mission(fund_id, second_id)
    await db_session.commit()
    assert (await client.get(f"/api/v1/funds/{fund_id}")).json()["lockedByMissionId"] == str(first_id)

    await service.release_from_mission(fund_id, first_id)
    await db_session.commit()
    available = await client.get("/api/v1/funds/available")
    assert [f["id"] for f in available.json()["content"]] == [str(fund_id)]
