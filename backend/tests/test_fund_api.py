from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import EmploymentLevel
from app.core.exceptions import FundAmountError
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


async def _make_mission(db_session: AsyncSession, requester: User, **overrides):
    mission = make_mission(requester_id=requester.id, fund_manager_id=requester.id, **overrides)
    db_session.add(mission)
    await db_session.commit()
    return mission


async def _charge(db_session: AsyncSession, fund_id: UUID, mission, amount: Decimal | None = None):
    service = FundService(db_session, FundRepository(db_session))
    await service.reserve_for_mission(fund_id, mission.id, amount or mission.estimated_cost)
    mission.fund_id = fund_id
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_fund_by_mission_success(client: AsyncClient, teacher: User, db_session: AsyncSession):
    fund_id = (await client.post("/api/v1/funds", json={"name": "Fondo Missione", "amount": "1000"})).json()["id"]
    mission = await _make_mission(db_session, teacher)
    await _charge(db_session, UUID(fund_id), mission)

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
    foreign_fund = make_fund(responsible_fc=other_user.fiscal_code, name="Fondo Altro", amount=Decimal("500"))
    db_session.add(foreign_fund)
    await db_session.commit()
    mission = await _make_mission(db_session, other_user)
    await _charge(db_session, foreign_fund.id, mission)

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


async def test_fund_finances_several_missions_until_its_remaining_amount_runs_out(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = UUID((await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "300"})).json()["id"])
    first, second, third = [await _make_mission(db_session, teacher) for _ in range(3)]

    await _charge(db_session, fund_id, first)
    await _charge(db_session, fund_id, second)
    service = FundService(db_session, FundRepository(db_session))
    with pytest.raises(FundAmountError, match=r"has € 59\.00 available, but the mission requires € 120\.50"):
        await service.reserve_for_mission(fund_id, third.id, third.estimated_cost)

    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["committedAmount"] == "241.00"
    assert fund["remainingAmount"] == "59.00"
    assert {m["id"] for m in fund["missions"]} == {str(first.id), str(second.id)}
    available = (await client.get("/api/v1/funds/available")).json()["content"]
    assert [f["id"] for f in available] == [str(fund_id)]



async def test_financed_missions_are_listed_from_the_oldest_request(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = UUID((await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "1000"})).json()["id"])
    requested_on = [datetime(2026, 10, 20), datetime(2026, 9, 1), datetime(2026, 10, 5)]
    missions = [await _make_mission(db_session, teacher, created_at=day) for day in requested_on]
    for mission in missions:
        await _charge(db_session, fund_id, mission)

    listed = (await client.get(f"/api/v1/funds/{fund_id}")).json()["missions"]
    assert [m["requestedAt"][:10] for m in listed] == ["2026-09-01", "2026-10-05", "2026-10-20"]

async def test_releasing_a_mission_gives_its_cost_back_to_the_fund(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = UUID((await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "1000"})).json()["id"])
    mission = await _make_mission(db_session, teacher)
    await _charge(db_session, fund_id, mission, Decimal("300.00"))
    service = FundService(db_session, FundRepository(db_session))

    await service.release_from_mission(fund_id, mission.id, Decimal("300.00"))
    await db_session.commit()
    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["committedAmount"] == "0.00"
    assert fund["remainingAmount"] == "1000.00"

    with pytest.raises(FundAmountError):
        await service.release_from_mission(fund_id, mission.id, Decimal("0.01"))


async def test_reserving_commits_the_mission_cost(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = UUID((await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "1000"})).json()["id"])
    mission = await _make_mission(db_session, teacher)
    await _charge(db_session, fund_id, mission, Decimal("300.00"))

    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["amount"] == "1000.00"
    assert fund["committedAmount"] == "300.00"
    assert fund["remainingAmount"] == "700.00"


async def test_reserving_beyond_the_remaining_amount_is_refused(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = UUID((await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "1000"})).json()["id"])
    mission = await _make_mission(db_session, teacher)
    service = FundService(db_session, FundRepository(db_session))

    with pytest.raises(FundAmountError, match=r"has € 1000\.00 available, but the mission requires € 1500\.00"):
        await service.reserve_for_mission(fund_id, mission.id, Decimal("1500.00"))

    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["missions"] == []
    assert fund["committedAmount"] == "0.00"
    assert fund["remainingAmount"] == "1000.00"


async def test_fund_manager_disappears_when_all_funds_are_exhausted(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_ids = [
        UUID((await client.post("/api/v1/funds", json={"name": name, "amount": "120.50"})).json()["id"])
        for name in ("Fondo A", "Fondo B")
    ]

    await _charge(db_session, fund_ids[0], await _make_mission(db_session, teacher))
    managers = (await client.get("/api/v1/users/fund-managers")).json()
    assert [u["fiscalCode"] for u in managers] == [teacher.fiscal_code]

    await _charge(db_session, fund_ids[1], await _make_mission(db_session, teacher))
    assert (await client.get("/api/v1/users/fund-managers")).json() == []


async def test_missions_on_own_fund_are_charged_at_creation(client: AsyncClient, teacher: User):
    fund_id = (await client.post("/api/v1/funds", json={"name": "Mio", "amount": "500"})).json()["id"]
    start = (datetime.now() + timedelta(days=30)).replace(hour=8, minute=0, second=0, microsecond=0)
    body = {
        "missionType": "RESEARCH", "subject": "Convegno", "destination": "Roma",
        "estimatedCost": "100", "startsAt": start.isoformat(), "endsAt": (start + timedelta(days=1, hours=12)).isoformat(),
        "fundManagerId": str(teacher.id), "fundId": fund_id,
    }
    first = await client.post("/api/v1/missions", json=body)
    second = await client.post("/api/v1/missions", json=body)
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["status"] == "ACCEPTED"
    assert first.json()["fundId"] == fund_id

    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["committedAmount"] == "200.00"
    assert {m["id"] for m in fund["missions"]} == {first.json()["id"], second.json()["id"]}

    too_expensive = await client.post("/api/v1/missions", json=body | {"estimatedCost": "400"})
    assert too_expensive.status_code == 400
    assert too_expensive.json()["message"] == 'Fund "Mio" has € 300.00 available, but the mission requires € 400.00'


async def test_manager_accepts_several_missions_on_the_same_fund(
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
    fund_id = (await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "1000"})).json()["id"]
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

    for mission_id in missions:
        accepted = await accept(mission_id, {"fundId": fund_id, "response": "Ok"})
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "ACCEPTED"
        assert accepted.json()["fundId"] == fund_id

    fund = (await client.get(f"/api/v1/funds/{fund_id}")).json()
    assert fund["committedAmount"] == "241.00"
    assert {m["id"] for m in fund["missions"]} == set(missions)


async def test_my_funds_show_the_financed_missions_and_force_delete_it(
    client: AsyncClient, db_session: AsyncSession, teacher: User
):
    fund_id = (await client.post("/api/v1/funds", json={"name": "Fondo", "amount": "200"})).json()["id"]
    mission = await _make_mission(
        db_session, teacher, subject="Convegno", estimated_cost=Decimal("150.00"),
    )
    await _charge(db_session, UUID(fund_id), mission)

    fund = (await client.get("/api/v1/funds")).json()["content"][0]
    assert fund["missions"] == [{
        "id": str(mission.id), "subject": "Convegno", "status": "PENDING",
        "estimatedCost": "150.00", "requesterName": "Mario Rossi",
        "requestedAt": mission.created_at.isoformat(), "refundStatus": None, "refundAmount": None,
    }]

    assert (await client.delete(f"/api/v1/funds/{fund_id}")).status_code == 409
    for obj in list(db_session.identity_map.values()):
        await db_session.refresh(obj)
    assert (await client.delete(f"/api/v1/funds/{fund_id}", params={"force": "true"})).status_code == 204
    assert (await client.get(f"/api/v1/funds/{fund_id}")).status_code == 404
    assert (await client.get(f"/api/v1/missions/{mission.id}")).status_code == 200


async def test_mission_in_the_past_is_rejected(client: AsyncClient, teacher: User):
    start = datetime.now() - timedelta(days=1)
    response = await client.post("/api/v1/missions", json={
        "missionType": "RESEARCH", "subject": "Convegno", "destination": "Roma",
        "estimatedCost": "100", "startsAt": start.replace(microsecond=0).isoformat(),
        "endsAt": (start + timedelta(days=3)).replace(microsecond=0).isoformat(),
        "fundManagerId": str(teacher.id),
    })
    assert response.status_code == 400
    assert "future" in response.json()["message"]
