from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (EmploymentLevel,ExpenseCategory,ExpenseSubtype,MissionStatus,MissionType,RefundStatus)
from app.db.mission import Mission
from app.db.models import User
from app.schemas.refund import MAX_EXPENSE_AMOUNT, RefundItemCreateDTO
from app.security import current_active_user
from app.db.refund_item import RefundItem
from app.db.refund_request import RefundRequest
from main import app


@pytest.fixture
async def requester(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email="requester@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        name="Mario",
        surname="Rossi",
        fiscal_code="RSSMRA80A01H501U",
        employment_level=EmploymentLevel.RICERCATORE,
        department="Informatica",
    )
    db_session.add(user)
    await db_session.commit()
    app.dependency_overrides[current_active_user] = lambda: user
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email="other@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        name="Luigi",
        surname="Verdi",
        fiscal_code="VRDLGI85B02F205X",
        employment_level=EmploymentLevel.RICERCATORE,
        department="Fisica",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=True,
        is_verified=True,
        name="Admin",
        surname="Super",
        fiscal_code="ADMSRV80A01H501U",
        employment_level=EmploymentLevel.PROFESSORE_ORDINARIO,
        department="Amministrazione",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def create_mission(
    db_session: AsyncSession,
    requester_id: UUID,
    fund_manager_id: UUID | None = None,
    status: MissionStatus = MissionStatus.ACCEPTED,
    ended: bool = True,
) -> Mission:
    now = datetime.now()
    starts_at = now - timedelta(days=3) if ended else now - timedelta(hours=2)
    ends_at = now - timedelta(hours=2) if ended else now + timedelta(days=2)

    mission = Mission(
        id=uuid4(),
        mission_type=MissionType.RESEARCH,
        status=status,
        subject="Conferenza di Ricerca",
        destination="Roma",
        estimated_cost=Decimal("250.00"),
        starts_at=starts_at,
        ends_at=ends_at,
        requester_id=requester_id,
        fund_manager_id=fund_manager_id or requester_id,
    )
    db_session.add(mission)
    await db_session.commit()
    return mission


# test endpoint POST /api/v1/refunds (creazione richiesta refund)

@pytest.mark.asyncio
async def test_create_refund_request_happy_path(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)

    response = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    assert response.status_code == 201
    data = response.json()
    assert data["missionId"] == str(mission.id)
    assert data["status"] == "DRAFT"
    assert data["totalRequestedAmount"] == "0.00"
    assert data["totalReimbursedAmount"] == "0.00"
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_refund_request_invalid_dto_missing_mission_id(client: AsyncClient, requester: User):
    response = await client.post("/api/v1/refunds", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_refund_request_invalid_dto_malformed_uuid(client: AsyncClient, requester: User):
    response = await client.post("/api/v1/refunds", json={"missionId": "not-a-valid-uuid"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_refund_request_invalid_dto_extra_fields(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    response = await client.post(
        "/api/v1/refunds",
        json={"missionId": str(mission.id), "unknownField": "malicious_payload"},
    )
    assert response.status_code == 422



@pytest.mark.asyncio
async def test_create_refund_request_fails_if_mission_not_ended(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=False)

    response = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_refund_request_fails_if_mission_not_accepted(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, status=MissionStatus.PENDING, ended=True)
    response = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_refund_request_fails_if_not_requester(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    app.dependency_overrides[current_active_user] = lambda: other_user

    response = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_refund_request_fails_if_mission_not_found(client: AsyncClient, requester: User):
    response = await client.post("/api/v1/refunds", json={"missionId": str(uuid4())})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_refund_request_fails_if_already_exists(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)

    first_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    assert first_res.status_code == 201

    second_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    assert second_res.status_code == 400


#TEST endpoint GET /api/v1/refunds/by-mission/{mission_id}

@pytest.mark.asyncio
async def test_get_refund_by_mission_happy_path_requester(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    response = await client.get(f"/api/v1/refunds/by-mission/{mission.id}")

    assert response.status_code == 200
    assert response.json()["id"] == refund_id


@pytest.mark.asyncio
async def test_get_refund_by_mission_happy_path_admin(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.get(f"/api/v1/refunds/by-mission/{mission.id}")

    assert response.status_code == 200
    assert response.json()["id"] == refund_id


@pytest.mark.asyncio
async def test_get_refund_by_mission_returns_null_if_none_created(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)

    response = await client.get(f"/api/v1/refunds/by-mission/{mission.id}")

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_get_refund_by_mission_invalid_uuid(client: AsyncClient, requester: User):
    response = await client.get("/api/v1/refunds/by-mission/not-a-valid-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_refund_by_mission_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    app.dependency_overrides[current_active_user] = lambda: other_user
    response = await client.get(f"/api/v1/refunds/by-mission/{mission.id}")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_refund_by_mission_not_found_for_missing_mission(client: AsyncClient, requester: User):
    response = await client.get(f"/api/v1/refunds/by-mission/{uuid4()}")
    assert response.status_code == 404


#TEST endpoint GET /api/v1/refunds/{refund_id}

@pytest.mark.asyncio
async def test_get_refund_by_id_happy_path_requester(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    response = await client.get(f"/api/v1/refunds/{refund_id}")

    assert response.status_code == 200
    assert response.json()["id"] == refund_id


@pytest.mark.asyncio
async def test_get_refund_by_id_happy_path_admin(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.get(f"/api/v1/refunds/{refund_id}")

    assert response.status_code == 200
    assert response.json()["id"] == refund_id


@pytest.mark.asyncio
async def test_get_refund_by_id_invalid_uuid(client: AsyncClient, requester: User):
    response = await client.get("/api/v1/refunds/not-a-valid-uuid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_refund_by_id_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: other_user
    response = await client.get(f"/api/v1/refunds/{refund_id}")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_refund_by_id_not_found(client: AsyncClient, requester: User):
    response = await client.get(f"/api/v1/refunds/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_fund_manager_cannot_view_refund(
    client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User
):
    mission = await create_mission(db_session, requester.id, fund_manager_id=other_user.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: other_user

    res_by_mission = await client.get(f"/api/v1/refunds/by-mission/{mission.id}")
    assert res_by_mission.status_code == 403

    res_by_id = await client.get(f"/api/v1/refunds/{refund_id}")
    assert res_by_id.status_code == 403

# TEST endpoint GET /api/v1/refunds/{refund_id}/review (admin review)

#test happy path, l'admin legge la richiesta di rimborso
@pytest.mark.asyncio
async def test_get_refund_review_happy_path_admin(client, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True) #creo una missione conclusa
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)}) # creo una richiesta per quella missione
    refund_id = post_res.json()["id"] #estraggo l'id
    refund = await db_session.get(RefundRequest,UUID(refund_id))  # la porto in SUBMITTED: le DRAFT non sono visibili all'admin
    refund.status = RefundStatus.SUBMITTED
    app.dependency_overrides[current_active_user] = lambda: admin_user #switcho ad admin
    response = await client.get(f"/api/v1/refunds/{refund_id}/review") #chiamo il mio endpoint

    assert response.status_code == 200 #verifico che la response sia 200
    data = response.json() #e che i dati corrispondano effettivamente a quelli della missione creata
    assert data["id"] == refund_id
    assert data["mission"]["id"] == str(mission.id)
    assert data["mission"]["subject"] == "Conferenza di Ricerca"
    assert data["mission"]["estimatedCost"] == "250.00"
    assert data["mission"]["requester"]["name"] == "Mario"
    assert data["mission"]["requester"]["surname"] == "Rossi"
    assert data["mission"]["requester"]["department"] == "Informatica"
    assert data["items"] == []

# happy path con gli items
@pytest.mark.asyncio
async def test_get_refund_review_includes_items(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund = RefundRequest(mission_id=mission.id, status=RefundStatus.SUBMITTED) #creo la richiesta relativa alla missione senza salvare nel db
    db_session.add(refund)
    await db_session.flush()
    #al momento aggiungo l'item a mano perchè non esiste l'endpoint specifico (lo cambierò)
    db_session.add(RefundItem(
        refund_request_id=refund.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=datetime(2026, 11, 1, 13, 0),
        requested_amount=Decimal("25.50"),
        receipt_file_path="missions/test/lunch.pdf",
        receipt_original_filename="lunch.pdf",
        description="Lunch",
    ))
    await db_session.commit()
    #switcho ad admin
    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.get(f"/api/v1/refunds/{refund.id}/review")

    #verifico tutto
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["category"] == "MEALS"
    assert items[0]["requestedAmount"] == "25.50"
    assert items[0]["reimbursedAmount"] is None

#test utente normale  prova a leggere la richiesta di rimborso --> 403
@pytest.mark.asyncio
async def test_get_refund_review_forbidden_for_non_admin(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    response = await client.get(f"/api/v1/refunds/{refund_id}/review")

    assert response.status_code == 403

#se la richiesta di rimborso non esiste (generando un id random) --> 404
@pytest.mark.asyncio
async def test_get_refund_review_not_found(client: AsyncClient, admin_user: User):
    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.get(f"/api/v1/refunds/{uuid4()}/review")
    assert response.status_code == 404

#se la richiesta è ancora in bozza (DRAFT) l'admin non la vede --> 404
@pytest.mark.asyncio
async def test_get_refund_review_draft_not_visible_to_admin(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.get(f"/api/v1/refunds/{refund_id}/review")

    assert response.status_code == 404
# TEST vincoli dei campi per i subtype di spesa

def test_refund_item_transport_validation():
    now = datetime.now()

    #valido
    item = RefundItemCreateDTO(
        category=ExpenseCategory.TRANSPORT,
        subtype=ExpenseSubtype.TRAIN,
        itinerary_from="Paola",
        itinerary_to="Roma",
        starts_at=now,
        ends_at=now + timedelta(hours=4),
        requested_amount=Decimal("50.00"),
        description="Frecciarossa andata",
    )
    assert item.itinerary_from == "Paola"
    assert item.itinerary_to == "Roma"

    # errore per trasporto senza itinerario
    with pytest.raises(ValueError):
        RefundItemCreateDTO(
            category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN,
            starts_at=now,
            ends_at=now + timedelta(hours=4),
            requested_amount=Decimal("50.00"),
            description="Treno senza Da/A",
        )

    # Trasporto senza orario di arrivo
    with pytest.raises(ValueError):
        RefundItemCreateDTO(
            category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN,
            itinerary_from="Paola",
            itinerary_to="Roma",
            starts_at=now,
            ends_at=None,
            requested_amount=Decimal("50.00"),
            description="Treno senza orario arrivo",
        )

    # Trasporto con data arrivo precedente a partenza
    with pytest.raises(ValueError):
        RefundItemCreateDTO(
            category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN,
            itinerary_from="Paola",
            itinerary_to="Roma",
            starts_at=now,
            ends_at=now - timedelta(hours=1),
            requested_amount=Decimal("50.00"),
            description="Treno indietro nel tempo",
        )


def test_refund_item_accommodation_validation():
    now = datetime.now()

    # Alloggio valido
    item = RefundItemCreateDTO(
        category=ExpenseCategory.ACCOMMODATION,
        subtype=ExpenseSubtype.ACCOMMODATION_EXPENSE,
        starts_at=now,
        ends_at=now + timedelta(days=2),
        requested_amount=Decimal("120.00"),
        description="Hotel 2 notti",
    )
    assert item.ends_at is not None

    # Alloggio con itinerario
    with pytest.raises(ValueError, match="Itinerary is not allowed for accommodation"):
        RefundItemCreateDTO(
            category=ExpenseCategory.ACCOMMODATION,
            subtype=ExpenseSubtype.ACCOMMODATION_EXPENSE,
            itinerary_from="Roma",
            starts_at=now,
            ends_at=now + timedelta(days=2),
            requested_amount=Decimal("120.00"),
            description="Hotel con itinerario",
        )

    # Alloggio senza data di fine: errore
    with pytest.raises(ValueError, match="Check-out time .* is required for accommodation"):
        RefundItemCreateDTO(
            category=ExpenseCategory.ACCOMMODATION,
            subtype=ExpenseSubtype.ACCOMMODATION_EXPENSE,
            starts_at=now,
            ends_at=None,
            requested_amount=Decimal("120.00"),
            description="Hotel senza checkout",
        )

    # Alloggio con check-out precedente a check-in
    with pytest.raises(ValueError, match="Check-out time must be after check-in time"):
        RefundItemCreateDTO(
            category=ExpenseCategory.ACCOMMODATION,
            subtype=ExpenseSubtype.ACCOMMODATION_EXPENSE,
            starts_at=now,
            ends_at=now - timedelta(days=1),
            requested_amount=Decimal("120.00"),
            description="Hotel indietro nel tempo",
        )


def test_refund_item_meals_validation():
    now = datetime.now()

    # Vitto valido
    item = RefundItemCreateDTO(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("25.00"),
        description="Pranzo di lavoro",
    )
    assert item.ends_at is None
    assert item.itinerary_from is None

    # Vitto con itinerario: errore
    with pytest.raises(ValueError, match="Itinerary is not allowed for MEALS"):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            itinerary_from="Roma",
            starts_at=now,
            requested_amount=Decimal("25.00"),
            description="Pranzo",
        )

    # Vitto con data fine: errore
    with pytest.raises(ValueError, match="End time .* is not allowed for MEALS"):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            requested_amount=Decimal("25.00"),
            description="Pranzo con orario fine",
        )


def test_refund_item_other_validation():
    now = datetime.now()

    # Spesa "Altro" valida
    item = RefundItemCreateDTO(
        category=ExpenseCategory.OTHER,
        starts_at=now,
        requested_amount=Decimal("150.00"),
        description="Quota iscrizione congresso",
    )
    assert item.subtype is None
    assert item.ends_at is None
    assert item.itinerary_from is None

    # "Altro" con subtype fornito: errore
    with pytest.raises(ValueError, match="Subtype is not allowed for OTHER"):
        RefundItemCreateDTO(
            category=ExpenseCategory.OTHER,
            subtype=ExpenseSubtype.TRAIN,
            starts_at=now,
            requested_amount=Decimal("150.00"),
            description="Altra spesa con subtype non ammesso",
        )

    with pytest.raises(ValueError, match="Itinerary is not allowed for OTHER"):
        RefundItemCreateDTO(
            category=ExpenseCategory.OTHER,
            itinerary_from="Roma",
            starts_at=now,
            requested_amount=Decimal("150.00"),
            description="Iscrizione con itinerario",
        )

    with pytest.raises(ValueError, match="End time .* is not allowed for OTHER"):
        RefundItemCreateDTO(
            category=ExpenseCategory.OTHER,
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            requested_amount=Decimal("150.00"),
            description="Iscrizione con orario fine",
        )

    with pytest.raises(ValueError, match="Valid transport subtype is required"):
        RefundItemCreateDTO(
            category=ExpenseCategory.TRANSPORT,
            itinerary_from="Paola",
            itinerary_to="Roma",
            starts_at=now,
            ends_at=now + timedelta(hours=4),
            requested_amount=Decimal("50.00"),
            description="Trasporto senza subtype",
        )


def test_refund_item_amount_and_description_validation():
    now = datetime.now()

    # Richiesto 0€
    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("0.00"),
            description="Pasto gratis",
        )

    # Importo negativo
    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("-10.00"),
            description="Pasto negativo",
        )

    # Descrizione vuota non consentita
    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("20.00"),
            description="",
        )


def test_refund_item_boundary_cases_amounts():
    now = datetime.now()

    min_item = RefundItemCreateDTO(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("0.01"),
        description="Caffè minimo",
    )
    assert min_item.requested_amount == Decimal("0.01")

    max_item = RefundItemCreateDTO(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=MAX_EXPENSE_AMOUNT,
        description="Spesa al limite massimo",
    )
    assert max_item.requested_amount == Decimal("10000.00")

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=MAX_EXPENSE_AMOUNT + Decimal("0.01"),
            description="Oltre il tetto massimo",
        )

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.555"),
            description="Troppi decimali",
        )


def test_refund_item_boundary_cases_lengths():
    now = datetime.now()

    item_min_desc = RefundItemCreateDTO(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("10.00"),
        description="A",
    )
    assert len(item_min_desc.description) == 1

    item_max_desc = RefundItemCreateDTO(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("10.00"),
        description="D" * 255,
    )
    assert len(item_max_desc.description) == 255

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            description="D" * 256,
        )

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            description="    ",
        )

    item_max_itinerary = RefundItemCreateDTO(
        category=ExpenseCategory.TRANSPORT,
        subtype=ExpenseSubtype.TRAIN,
        itinerary_from="A" * 255,
        itinerary_to="B" * 255,
        starts_at=now,
        ends_at=now + timedelta(hours=2),
        requested_amount=Decimal("50.00"),
        description="Treno itinerario limite",
    )
    assert len(item_max_itinerary.itinerary_from) == 255
    assert len(item_max_itinerary.itinerary_to) == 255

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN,
            itinerary_from="A" * 256,
            itinerary_to="Roma",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            requested_amount=Decimal("50.00"),
            description="Itinerario troppo lungo",
        )

    item_curr = RefundItemCreateDTO(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("10.00"),
        currency="USD",
        description="Pranzo estero",
    )
    assert item_curr.currency == "USD"

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            currency="EU",
            description="Valuta 2 char",
        )

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            currency="EURO",
            description="Valuta 4 char",
        )
