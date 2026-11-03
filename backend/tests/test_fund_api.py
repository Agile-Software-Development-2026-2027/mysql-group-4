from decimal import Decimal
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
from tests.factories import make_fund, make_mission


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

    by_mission = await client.get(f"/api/v1/funds/by-mission/{uuid4()}")
    assert by_mission.status_code == 200
    assert by_mission.json() is None

    deleted = await client.delete(f"/api/v1/funds/{fund_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/funds/{fund_id}")).status_code == 404


async def test_create_fund_rejects_negative_amount(client: AsyncClient, teacher: User):
    response = await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "-5"})
    assert response.status_code == 422


async def test_funds_require_login(client: AsyncClient):
    assert (await client.get("/api/v1/funds")).status_code == 401
    assert (await client.get(f"/api/v1/funds/by-mission/{uuid4()}")).status_code == 401


@pytest.mark.asyncio
async def test_get_fund_by_mission_success(client: AsyncClient, teacher: User, db_session: AsyncSession):
    fund_id = (await client.post("/api/v1/funds", json={"name": "Fondo Missione", "amount": "1000"})).json()["id"]
    mission = make_mission(requester_id=teacher.id, fund_manager_id=teacher.id)
    db_session.add(mission)
    await db_session.commit()

    service = FundService(db_session, FundRepository(db_session))
    await service.lock_for_mission(UUID(fund_id), mission.id)
    await db_session.commit()

    response = await client.get(f"/api/v1/funds/by-mission/{mission.id}")
    assert response.status_code == 200
    assert response.json()["id"] == fund_id
    assert response.json()["name"] == "Fondo Missione"


@pytest.mark.asyncio
async def test_get_fund_by_mission_validation_error(client: AsyncClient, teacher: User):
    response = await client.get("/api/v1/funds/by-mission/not-a-valid-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_fund_by_mission_forbidden(client: AsyncClient, teacher: User, db_session: AsyncSession):
    other_user = User(
        id=uuid4(), email="altro.utente@example.com", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
        name="Altro", surname="Utente", fiscal_code="OTRUSR85M01H501Z",
        employment_level=EmploymentLevel.RICERCATORE, department="Fisica",
    )
    db_session.add(other_user)
    await db_session.commit()

    foreign_fund = make_fund(responsible_fc=other_user.fiscal_code, name="Fondo Altro", amount=Decimal("500") if 'Decimal' in globals() else 500)
    db_session.add(foreign_fund)
    mission = make_mission(requester_id=other_user.id, fund_manager_id=other_user.id)
    db_session.add(mission)
    await db_session.commit()

    service = FundService(db_session, FundRepository(db_session))
    await service.lock_for_mission(foreign_fund.id, mission.id)
    await db_session.commit()

    response = await client.get(f"/api/v1/funds/by-mission/{mission.id}")
    assert response.status_code == 403


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
    for obj in list(db_session.identity_map.values()):
        await db_session.refresh(obj)

    await service.release_from_mission(fund_id, second_id)
    await db_session.commit()
    assert (await client.get(f"/api/v1/funds/{fund_id}")).json()["lockedByMissionId"] == str(first_id)

    await service.release_from_mission(fund_id, first_id)
    await db_session.commit()
    available = await client.get("/api/v1/funds/available")
    assert [f["id"] for f in available.json()["content"]] == [str(fund_id)]


async def test_fund_manager_disappears_when_all_funds_are_assigned(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_ids = [
        UUID((await client.post("/api/v1/funds", json={"name": name, "amount": "10"})).json()["id"])
        for name in ("Fondo A", "Fondo B")
    ]
    service = FundService(db_session, FundRepository(db_session))

    await service.lock_for_mission(fund_ids[0], (await _make_mission(db_session, teacher)).id)
    await db_session.commit()
    managers = (await client.get("/api/v1/users/fund-managers")).json()
    assert [u["fiscalCode"] for u in managers] == [teacher.fiscal_code]

    await service.lock_for_mission(fund_ids[1], (await _make_mission(db_session, teacher)).id)
    await db_session.commit()
    assert (await client.get("/api/v1/users/fund-managers")).json() == []


async def test_mission_on_own_fund_locks_it_at_creation(client: AsyncClient, teacher: User):
    fund_id = (await client.post("/api/v1/funds", json={"name": "Mio", "amount": "500"})).json()["id"]
    body = {
        "missionType": "RESEARCH", "subject": "Convegno", "destination": "Roma",
        "estimatedCost": "100", "startsAt": "2026-12-01T08:00:00", "endsAt": "2026-12-02T20:00:00",
        "fundManagerId": str(teacher.id), "fundId": fund_id,
    }
    created = await client.post("/api/v1/missions", json=body)
    assert created.status_code == 201
    assert created.json()["status"] == "ACCEPTED"
    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["lockedByMissionId"] == created.json()["id"]

    second = await client.post("/api/v1/missions", json=body)
    assert second.status_code == 409


async def test_manager_accepts_a_mission_choosing_one_of_his_funds(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    other = User(
        id=uuid4(), email="luigi.verdi@example.com", hashed_password="x",
        is_active=True, is_superuser=False, is_verified=True,
        name="Luigi", surname="Verdi", fiscal_code="VRDLGI85B02F205X",
        employment_level=EmploymentLevel.RICERCATORE, department="Fisica",
    )
    db_session.add(other)
    await db_session.commit()
    other_id = other.id
    fund_id = (await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "100"})).json()["id"]
    missions = []
    for _ in range(2):
        mission = make_mission(requester_id=other_id, fund_manager_id=teacher.id)
        db_session.add(mission)
        missions.append(str(mission.id))
    foreign_fund = make_fund(responsible_fc=other.fiscal_code)
    db_session.add(foreign_fund)
    await db_session.commit()
    foreign_fund_id = str(foreign_fund.id)

    accept = lambda mission_id, body: client.patch(f"/api/v1/missions/{mission_id}/accept", json=body)
    assert (await accept(missions[0], {})).status_code == 422
    assert (await accept(missions[0], {"fundId": foreign_fund_id})).status_code == 403
    for obj in list(db_session.identity_map.values()):
        await db_session.refresh(obj)

    accepted = await accept(missions[0], {"fundId": fund_id, "response": "Ok"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    assert (await client.get(f"/api/v1/funds/{fund_id}")).json()["lockedByMissionId"] == missions[0]

    second = await accept(missions[1], {"fundId": fund_id})
    assert second.status_code == 409
async def test_my_funds_show_who_requested_a_locked_fund_and_force_delete_it(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = (await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "200"})).json()["id"]
    mission = make_mission(
        requester_id=teacher.id, fund_manager_id=teacher.id,
        subject="Convegno", estimated_cost=Decimal("150.00"),
    )
    db_session.add(mission)
    await db_session.commit()
    mission_id = mission.id
    await FundService(db_session, FundRepository(db_session)).lock_for_mission(UUID(fund_id), mission_id)
    await db_session.commit()

    fund = (await client.get("/api/v1/funds")).json()["content"][0]
    assert fund["requestedAmount"] == "150.00"
    assert fund["requesterName"] == "Mario Rossi"
    assert fund["missionSubject"] == "Convegno"
    assert (await client.get(f"/api/v1/funds/{fund_id}")).json()["requesterName"] == "Mario Rossi"

    assert (await client.delete(f"/api/v1/funds/{fund_id}")).status_code == 409
    for obj in list(db_session.identity_map.values()):
        await db_session.refresh(obj)
    assert (await client.delete(f"/api/v1/funds/{fund_id}", params={"force": "true"})).status_code == 204
    assert (await client.get(f"/api/v1/funds/{fund_id}")).status_code == 404
    assert (await client.get(f"/api/v1/missions/{mission_id}")).status_code == 200
