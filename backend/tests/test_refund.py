import io
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.enums import (EmploymentLevel,ExpenseCategory,ExpenseSubtype,MissionStatus,MissionType,RefundStatus)
from app.db.fund import Fund
from app.db.mission import Mission
from app.db.models import User
from app.schemas.refund import MAX_EXPENSE_AMOUNT, RefundItemCreateDTO, RefundRequestDTO
from app.security import current_active_user
from app.db.refund_item import RefundItem
from app.db.refund_request import RefundRequest
from main import app

import json
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from app.api.deps import get_receipt_ai_service
from app.schemas.receipt_ai import BoundingBoxDTO, ReceiptDetectionResponseDTO, ReceiptPageDTO
from app.services.currency_service import CurrencyConversionService
from app.services.receipt_ai_service import ReceiptAIService


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
    started: bool = True,
) -> Mission:
    now = datetime.now()
    if not started:
        starts_at = now + timedelta(days=1)
        ends_at = now + timedelta(days=3)
    elif ended:
        starts_at = now - timedelta(days=3)
        ends_at = now - timedelta(hours=2)
    else:
        starts_at = now - timedelta(hours=2)
        ends_at = now + timedelta(days=2)

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
async def test_create_refund_request_fails_if_mission_not_accepted(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, status=MissionStatus.PENDING, ended=True)
    response = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_refund_request_fails_if_mission_not_started(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, started=False, ended=False)

    response = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    assert response.status_code == 400
    assert "started" in response.json()["message"].lower()


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

# TEST endpoint PATCH /api/v1/refunds/{refund_id}/approve (admin approval)

async def create_submitted_refund(db_session: AsyncSession, mission_id: UUID) -> tuple[RefundRequest, RefundItem]:
    refund = RefundRequest(mission_id=mission_id, status=RefundStatus.SUBMITTED)
    db_session.add(refund)
    await db_session.flush()
    item = RefundItem(
        refund_request_id=refund.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=datetime(2026, 11, 1, 13, 0),
        requested_amount=Decimal("25.50"),
        receipt_file_path="missions/test/lunch.pdf",
        receipt_original_filename="lunch.pdf",
        description="Lunch",
    )
    db_session.add(item)
    await db_session.commit()
    return refund, item


def approve_payload(item_id: UUID) -> dict:
    return {"items": [{"itemId": str(item_id), "reimbursedAmount": "20.00", "adminNotes": "Max 20 EUR per meal"}]}

#happy path: l'admin approva, la richiesta diventa APPROVED e la missione COMPLETED
@pytest.mark.asyncio
async def test_approve_refund_happy_path(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund, item = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.patch(f"/api/v1/refunds/{refund.id}/approve", json=approve_payload(item.id))

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["totalReimbursedAmount"] == "20.00"
    assert data["items"][0]["reimbursedAmount"] == "20.00"
    assert data["items"][0]["adminNotes"] == "Max 20 EUR per meal"

    await db_session.refresh(mission)
    assert mission.status == MissionStatus.COMPLETED


#una richiesta già approvata non si può approvare di nuovo --> 400
@pytest.mark.asyncio
async def test_approve_refund_already_approved(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund, item = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: admin_user
    first = await client.patch(f"/api/v1/refunds/{refund.id}/approve", json=approve_payload(item.id))
    assert first.status_code == 200

    second = await client.patch(f"/api/v1/refunds/{refund.id}/approve", json=approve_payload(item.id))
    assert second.status_code == 400


#un utente normale non può approvare --> 403
@pytest.mark.asyncio
async def test_approve_refund_forbidden_for_non_admin(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund, item = await create_submitted_refund(db_session, mission.id)

    response = await client.patch(f"/api/v1/refunds/{refund.id}/approve", json=approve_payload(item.id))

    assert response.status_code == 403

# TEST endpoint POST /api/v1/refunds/{refund_id}/items

def make_valid_transport_item_payload(starts_at: datetime | None = None) -> dict:
    start = starts_at or datetime.now()
    end = start + timedelta(hours=3)
    return {
        "category": "TRANSPORT",
        "subtype": "TRAIN",
        "itineraryFrom": "Paola",
        "itineraryTo": "Roma Termini",
        "startsAt": start.isoformat(),
        "endsAt": end.isoformat(),
        "requestedAmount": 55.50,
        "currency": "EUR",
        "isTraceable": True,
        "receiptFilePath": "refunds/123/receipts/test_rec.pdf",
        "receiptOriginalFilename": "test_rec.pdf",
        "description": "Viaggio di andata in treno",
    }

@pytest.mark.asyncio
async def test_create_refund_item_happy_path_requester(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    assert post_refund.status_code == 201
    refund_id = post_refund.json()["id"]

    payload = make_valid_transport_item_payload()
    response = await client.post(f"/api/v1/refunds/{refund_id}/items", json=payload)

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_refund_item_invalid_payload(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    payload = make_valid_transport_item_payload()
    payload["requestedAmount"] = -10.00
    response = await client.post(f"/api/v1/refunds/{refund_id}/items", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_refund_item_not_found(client: AsyncClient, requester: User):
    payload = make_valid_transport_item_payload()
    response = await client.post(f"/api/v1/refunds/{uuid4()}/items", json=payload)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_create_refund_item_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: other_user
    payload = make_valid_transport_item_payload()
    response = await client.post(f"/api/v1/refunds/{refund_id}/items", json=payload)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_create_refund_item_error_when_submitted(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(post_refund.json()["id"])

    res = await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))
    db_refund = res.scalar_one()
    db_refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    payload = make_valid_transport_item_payload()
    response = await client.post(f"/api/v1/refunds/{refund_id}/items", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_refund_item_error_when_approved(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(post_refund.json()["id"])

    res = await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))
    db_refund = res.scalar_one()
    db_refund.status = RefundStatus.APPROVED
    await db_session.commit()

    payload = make_valid_transport_item_payload()
    response = await client.post(f"/api/v1/refunds/{refund_id}/items", json=payload)
    assert response.status_code == 400


def make_refund_item(**kwargs) -> RefundItemCreateDTO:
    kwargs.setdefault("receipt_file_path", "refunds/123/receipts/test.pdf")
    kwargs.setdefault("receipt_original_filename", "test.pdf")
    return RefundItemCreateDTO(**kwargs)


def test_refund_item_receipt_fields_validation():
    now = datetime.now()
    base_kwargs = {
        "category": ExpenseCategory.OTHER,
        "starts_at": now,
        "requested_amount": Decimal("10.00"),
        "description": "Test spesa",
    }

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(**base_kwargs)

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(**base_kwargs, receipt_file_path="", receipt_original_filename="rec.pdf")

    with pytest.raises(ValidationError):
        RefundItemCreateDTO(**base_kwargs, receipt_file_path="refunds/1/rec.pdf", receipt_original_filename="")

    valid = RefundItemCreateDTO(
        **base_kwargs,
        receipt_file_path="refunds/1/rec.pdf",
        receipt_original_filename="rec.pdf",
    )
    assert valid.receipt_file_path == "refunds/1/rec.pdf"
    assert valid.receipt_original_filename == "rec.pdf"

# TEST endpoint POST /api/v1/refunds/{refund_id}/receipts

@pytest.mark.asyncio
async def test_upload_receipt_happy_path(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    with patch("app.services.refund_service.minio_client") as mock_minio:
        mock_minio.put_object.return_value = None
        pdf_bytes = io.BytesIO(b"%PDF-1.4 Fake PDF Receipt Content")
        files = {"file": ("biglietto_treno.pdf", pdf_bytes, "application/pdf")}
        response = await client.post(f"/api/v1/refunds/{refund_id}/receipts", files=files)

        assert response.status_code == 201


@pytest.mark.asyncio
async def test_upload_receipt_invalid_file_extension(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    files = {"file": ("malware.exe", io.BytesIO(b"binary"), "application/octet-stream")}
    response = await client.post(f"/api/v1/refunds/{refund_id}/receipts", files=files)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_receipt_empty_file(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    files = {"file": ("vuoto.pdf", io.BytesIO(b""), "application/pdf")}
    response = await client.post(f"/api/v1/refunds/{refund_id}/receipts", files=files)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_receipt_file_too_large(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    large_content = b"a" * (10 * 1024 * 1024 + 1)
    files = {"file": ("scontrino_enorme.pdf", io.BytesIO(large_content), "application/pdf")}
    response = await client.post(f"/api/v1/refunds/{refund_id}/receipts", files=files)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_upload_receipt_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_refund.json()["id"]

    app.dependency_overrides[current_active_user] = lambda: other_user
    files = {"file": ("scontrino.pdf", io.BytesIO(b"fake pdf"), "application/pdf")}
    response = await client.post(f"/api/v1/refunds/{refund_id}/receipts", files=files)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_receipt_not_found(client: AsyncClient, requester: User):
    files = {"file": ("scontrino.pdf", io.BytesIO(b"fake pdf"), "application/pdf")}
    response = await client.post(f"/api/v1/refunds/{uuid4()}/receipts", files=files)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_receipt_error_when_submitted(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_refund = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(post_refund.json()["id"])

    res = await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))
    db_refund = res.scalar_one()
    db_refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    files = {"file": ("scontrino.pdf", io.BytesIO(b"fake pdf"), "application/pdf")}
    response = await client.post(f"/api/v1/refunds/{refund_id}/receipts", files=files)
    assert response.status_code == 400

# TEST endpoint GET /api/v1/refunds/{refund_id}/items/{item_id}/receipt (receipt download)

def mock_minio_file(content: bytes) -> MagicMock:
    response = MagicMock()
    response.read.return_value = content
    return response


#happy path: l'admin scarica lo scontrino di una voce
@pytest.mark.asyncio
async def test_download_receipt_success(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund, item = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: admin_user
    with patch("app.services.refund_service.minio_client") as mock_minio:
        mock_minio.get_object.return_value = mock_minio_file(b"%PDF-1.4 Mock receipt")
        response = await client.get(f"/api/v1/refunds/{refund.id}/items/{item.id}/receipt")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 Mock receipt"


#un utente che non è né admin né il richiedente --> 403
@pytest.mark.asyncio
async def test_download_receipt_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund, item = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: other_user
    response = await client.get(f"/api/v1/refunds/{refund.id}/items/{item.id}/receipt")

    assert response.status_code == 403


#voce che non appartiene alla richiesta --> 404
@pytest.mark.asyncio
async def test_download_receipt_item_not_found(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund, _ = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.get(f"/api/v1/refunds/{refund.id}/items/{uuid4()}/receipt")

    assert response.status_code == 404

# TEST vincoli dei campi per i subtype di spesa

def test_refund_item_transport_validation():
    now = datetime.now()

    #valido
    item = make_refund_item(
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
        make_refund_item(
            category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN,
            starts_at=now,
            ends_at=now + timedelta(hours=4),
            requested_amount=Decimal("50.00"),
            description="Treno senza Da/A",
        )

    # Trasporto senza orario di arrivo
    with pytest.raises(ValueError):
        make_refund_item(
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
        make_refund_item(
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
    item = make_refund_item(
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
        make_refund_item(
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
        make_refund_item(
            category=ExpenseCategory.ACCOMMODATION,
            subtype=ExpenseSubtype.ACCOMMODATION_EXPENSE,
            starts_at=now,
            ends_at=None,
            requested_amount=Decimal("120.00"),
            description="Hotel senza checkout",
        )

    # Alloggio con check-out precedente a check-in
    with pytest.raises(ValueError, match="Check-out time must be after check-in time"):
        make_refund_item(
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
    item = make_refund_item(
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
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            itinerary_from="Roma",
            starts_at=now,
            requested_amount=Decimal("25.00"),
            description="Pranzo",
        )

    # Vitto con data fine: errore
    with pytest.raises(ValueError, match="End time .* is not allowed for MEALS"):
        make_refund_item(
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
    item = make_refund_item(
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
        make_refund_item(
            category=ExpenseCategory.OTHER,
            subtype=ExpenseSubtype.TRAIN,
            starts_at=now,
            requested_amount=Decimal("150.00"),
            description="Altra spesa con subtype non ammesso",
        )

    with pytest.raises(ValueError, match="Itinerary is not allowed for OTHER"):
        make_refund_item(
            category=ExpenseCategory.OTHER,
            itinerary_from="Roma",
            starts_at=now,
            requested_amount=Decimal("150.00"),
            description="Iscrizione con itinerario",
        )

    with pytest.raises(ValueError, match="End time .* is not allowed for OTHER"):
        make_refund_item(
            category=ExpenseCategory.OTHER,
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            requested_amount=Decimal("150.00"),
            description="Iscrizione con orario fine",
        )

    with pytest.raises(ValueError, match="Valid transport subtype is required"):
        make_refund_item(
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
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("0.00"),
            description="Pasto gratis",
        )

    # Importo negativo
    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("-10.00"),
            description="Pasto negativo",
        )

    # Descrizione vuota non consentita
    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("20.00"),
            description="",
        )


def test_refund_item_boundary_cases_amounts():
    now = datetime.now()

    min_item = make_refund_item(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("0.01"),
        description="Caffè minimo",
    )
    assert min_item.requested_amount == Decimal("0.01")

    max_item = make_refund_item(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=MAX_EXPENSE_AMOUNT,
        description="Spesa al limite massimo",
    )
    assert max_item.requested_amount == Decimal("10000.00")

    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=MAX_EXPENSE_AMOUNT + Decimal("0.01"),
            description="Oltre il tetto massimo",
        )

    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.555"),
            description="Troppi decimali",
        )


def test_refund_item_boundary_cases_lengths():
    now = datetime.now()

    item_min_desc = make_refund_item(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("10.00"),
        description="A",
    )
    assert len(item_min_desc.description) == 1

    item_max_desc = make_refund_item(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("10.00"),
        description="D" * 255,
    )
    assert len(item_max_desc.description) == 255

    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            description="D" * 256,
        )

    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            description="    ",
        )

    item_max_itinerary = make_refund_item(
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
        make_refund_item(
            category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN,
            itinerary_from="A" * 256,
            itinerary_to="Roma",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            requested_amount=Decimal("50.00"),
            description="Itinerario troppo lungo",
        )

    item_curr = make_refund_item(
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=now,
        requested_amount=Decimal("10.00"),
        currency="USD",
        description="Pranzo estero",
    )
    assert item_curr.currency == "USD"

    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            currency="EU",
            description="Valuta 2 char",
        )

    with pytest.raises(ValidationError):
        make_refund_item(
            category=ExpenseCategory.MEALS,
            subtype=ExpenseSubtype.MEALS_EXPENSE,
            starts_at=now,
            requested_amount=Decimal("10.00"),
            currency="EURO",
            description="Valuta 4 char",
        )


@pytest.mark.asyncio
async def test_filter_refunds_happy_path_admin(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    assert post_res.status_code == 201

    res = await db_session.execute(select(RefundRequest).where(RefundRequest.mission_id == mission.id))
    refund = res.scalar_one()
    refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    app.dependency_overrides[current_active_user] = lambda: admin_user

    payload_submitted = {"status": "SUBMITTED"}
    response_submitted = await client.post("/api/v1/refunds/filter", json=payload_submitted)

    assert response_submitted.status_code == 200
    data_submitted = response_submitted.json()
    assert isinstance(data_submitted, list)
    assert len(data_submitted) == 1
    assert data_submitted[0]["status"] == "SUBMITTED"
    assert data_submitted[0]["subject"] == "Conferenza di Ricerca"

    refund.status = RefundStatus.APPROVED
    await db_session.commit()

    payload_approved = {"status": "APPROVED"}
    response_approved = await client.post("/api/v1/refunds/filter", json=payload_approved)

    assert response_approved.status_code == 200
    data_approved = response_approved.json()
    assert len(data_approved) == 1
    assert data_approved[0]["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_filter_refunds_returns_empty_when_no_match(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    res = await db_session.execute(select(RefundRequest).where(RefundRequest.mission_id == mission.id))
    refund = res.scalar_one()
    refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    app.dependency_overrides[current_active_user] = lambda: admin_user

    payload = {"status": "APPROVED"}
    response = await client.post("/api/v1/refunds/filter", json=payload)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_filter_refunds_forbidden_for_non_admin(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})

    res = await db_session.execute(select(RefundRequest).where(RefundRequest.mission_id == mission.id))
    refund = res.scalar_one()
    refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    app.dependency_overrides[current_active_user] = lambda: other_user

    payload = {"status": "SUBMITTED"}
    response = await client.post("/api/v1/refunds/filter", json=payload)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_filter_refunds_invalid_dto_malformed_status(client: AsyncClient, admin_user: User):
    app.dependency_overrides[current_active_user] = lambda: admin_user
    payload = {"status": "STATO_INESISTENTE"}
    response = await client.post("/api/v1/refunds/filter", json=payload)
    assert response.status_code == 422


def _make_test_item(refund_id: UUID, user_id: UUID, amount: Decimal = Decimal("20.00"), **kwargs) -> RefundItem:
    data = dict(
        refund_request_id=refund_id, category=ExpenseCategory.OTHER, starts_at=datetime.now(),
        requested_amount=amount, currency="EUR", is_traceable=True,
        receipt_file_path="receipts/r.pdf", receipt_original_filename="r.pdf",
        description="Spesa", created_by=user_id, updated_by=user_id,
    )
    data.update(kwargs)
    return RefundItem(**data)


@pytest.mark.asyncio
async def test_filter_refund_items_by_categories_and_sort(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    now = datetime.now()
    items = [
        _make_test_item(
            refund_id, requester.id, Decimal("50.00"), category=ExpenseCategory.TRANSPORT,
            subtype=ExpenseSubtype.TRAIN, itinerary_from="Roma", itinerary_to="Milano",
            starts_at=now, ends_at=now + timedelta(hours=3), description="Treno"
        ),
        _make_test_item(refund_id, requester.id, Decimal("20.00"), category=ExpenseCategory.MEALS, subtype=ExpenseSubtype.MEALS_EXPENSE),
        _make_test_item(refund_id, requester.id, Decimal("100.00"), category=ExpenseCategory.OTHER),
    ]
    db_session.add_all(items)
    await db_session.commit()

    resp_all = await client.post(f"/api/v1/refunds/{refund_id}/items/filter", json={})
    assert resp_all.status_code == 200 and resp_all.json()["totalElements"] == 3

    resp_filtered = await client.post(
        f"/api/v1/refunds/{refund_id}/items/filter",
        json={"categories": ["TRANSPORT", "OTHER"], "sortByAmount": "desc"},
    )
    assert resp_filtered.status_code == 200
    assert [Decimal(c["requestedAmount"]) for c in resp_filtered.json()["content"]] == [Decimal("100.00"), Decimal("50.00")]

    resp_asc = await client.post(f"/api/v1/refunds/{refund_id}/items/filter", json={"sortByAmount": "asc"})
    assert resp_asc.status_code == 200
    assert [Decimal(c["requestedAmount"]) for c in resp_asc.json()["content"]] == [Decimal("20.00"), Decimal("50.00"), Decimal("100.00")]


@pytest.mark.asyncio
async def test_filter_refund_items_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    app.dependency_overrides[current_active_user] = lambda: other_user
    resp = await client.post(f"/api/v1/refunds/{create_resp.json()['id']}/items/filter", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_refund_item_success_and_recalculates_total(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("40.00"), description="Vecchia descrizione")
    db_session.add(item)
    res = await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))
    refund = res.scalar_one()
    refund.total_requested_amount = Decimal("40.00")
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/refunds/{refund_id}/items/{item.id}",
        json={"requestedAmount": "65.50", "description": "Nuova descrizione"},
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["requestedAmount"]) == Decimal("65.50")
    assert resp.json()["description"] == "Nuova descrizione"

    await db_session.refresh(refund)
    assert refund.total_requested_amount == Decimal("65.50")


@pytest.mark.asyncio
async def test_update_refund_item_replacing_receipt_deletes_old_file(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("20.00"))
    db_session.add(item)
    await db_session.commit()

    with patch("app.services.refund_service.minio_client") as mock_minio:
        resp = await client.patch(
            f"/api/v1/refunds/{refund_id}/items/{item.id}",
            json={"receiptFilePath": "receipts/new.pdf", "receiptOriginalFilename": "new.pdf"},
        )
    assert resp.status_code == 200
    assert resp.json()["receiptFilePath"] == "receipts/new.pdf"
    mock_minio.remove_object.assert_called_once()
    assert mock_minio.remove_object.call_args.kwargs["object_name"] == "receipts/r.pdf"


@pytest.mark.asyncio
async def test_update_refund_item_without_new_receipt_keeps_file(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("20.00"))
    db_session.add(item)
    await db_session.commit()

    with patch("app.services.refund_service.minio_client") as mock_minio:
        resp = await client.patch(f"/api/v1/refunds/{refund_id}/items/{item.id}", json={"description": "Solo testo"})
    assert resp.status_code == 200
    mock_minio.remove_object.assert_not_called()


@pytest.mark.asyncio
async def test_update_refund_item_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("25.00"))
    db_session.add(item)
    await db_session.commit()

    app.dependency_overrides[current_active_user] = lambda: other_user
    resp = await client.patch(f"/api/v1/refunds/{refund_id}/items/{item.id}", json={"description": "Hack"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_refund_item_success_and_recalculates_total(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("35.00"))
    db_session.add(item)
    res = await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))
    refund = res.scalar_one()
    refund.total_requested_amount = Decimal("35.00")
    await db_session.commit()

    resp = await client.delete(f"/api/v1/refunds/{refund_id}/items/{item.id}")
    assert resp.status_code == 204

    deleted_item = await db_session.get(RefundItem, item.id)
    assert deleted_item is None
    await db_session.refresh(refund)
    assert refund.total_requested_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_delete_refund_item_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("15.00"))
    db_session.add(item)
    await db_session.commit()

    app.dependency_overrides[current_active_user] = lambda: other_user
    resp = await client.delete(f"/api/v1/refunds/{refund_id}/items/{item.id}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_refund_item_fails_when_refund_not_draft(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("20.00"))
    db_session.add(item)
    res = await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))
    refund = res.scalar_one()
    refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    resp = await client.delete(f"/api/v1/refunds/{refund_id}/items/{item.id}")
    assert resp.status_code == 400


# ==============================================================================
# TEST endpoint PATCH /api/v1/refunds/{refund_id}/submit
# ==============================================================================

@pytest.mark.asyncio
async def test_submit_refund_request_happy_path(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    assert post_res.status_code == 201
    refund_id = post_res.json()["id"]

    item_payload = make_valid_transport_item_payload()
    item_res = await client.post(f"/api/v1/refunds/{refund_id}/items", json=item_payload)
    assert item_res.status_code == 201

    response = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUBMITTED"
    assert data["submittedAt"] is not None


@pytest.mark.asyncio
async def test_submit_refund_request_forbidden_for_other_user(client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    item_payload = make_valid_transport_item_payload()
    await client.post(f"/api/v1/refunds/{refund_id}/items", json=item_payload)

    app.dependency_overrides[current_active_user] = lambda: other_user
    response = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_refund_request_not_found(client: AsyncClient, requester: User):
    response = await client.patch(f"/api/v1/refunds/{uuid4()}/submit")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_refund_request_fails_if_no_items(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    response = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert response.status_code == 400
    assert "items" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_submit_refund_request_fails_if_already_submitted(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = post_res.json()["id"]

    item_payload = make_valid_transport_item_payload()
    await client.post(f"/api/v1/refunds/{refund_id}/items", json=item_payload)

    first_submit = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert first_submit.status_code == 200

    second_submit = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert second_submit.status_code == 400


@pytest.mark.asyncio
async def test_submit_refund_request_fails_if_mission_not_ended(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, started=True, ended=False)
    post_res = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    assert post_res.status_code == 201
    refund_id = post_res.json()["id"]

    item_payload = make_valid_transport_item_payload()
    item_res = await client.post(f"/api/v1/refunds/{refund_id}/items", json=item_payload)
    assert item_res.status_code == 201

    response = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert response.status_code == 400
    assert "not ended" in response.json()["message"].lower()


# ==============================================================================
# TEST limite sul costo stimato e regolazione del fondo all'approvazione
# ==============================================================================

async def create_funded_mission(db_session: AsyncSession, requester: User) -> tuple[Mission, Fund]:
    # Fondo da 1000 con 250 già impegnati dalla missione (il suo costo stimato).
    mission = await create_mission(db_session, requester.id, ended=True)
    fund = Fund(
        name="Fondo Ricerca", amount=Decimal("1000.00"), committed_amount=mission.estimated_cost,
        responsible_fc=requester.fiscal_code,
    )
    db_session.add(fund)
    await db_session.flush()
    mission.fund_id = fund.id
    await db_session.commit()
    return mission, fund


@pytest.mark.asyncio
async def test_create_refund_item_fails_when_total_exceeds_estimated_cost(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    first = await client.post(f"/api/v1/refunds/{refund_id}/items", json=make_valid_transport_item_payload())
    assert first.status_code == 201

    too_much = make_valid_transport_item_payload() | {"requestedAmount": 200.00}
    response = await client.post(f"/api/v1/refunds/{refund_id}/items", json=too_much)
    assert response.status_code == 400
    assert "estimated cost" in response.json()["message"]


@pytest.mark.asyncio
async def test_update_refund_item_fails_when_total_exceeds_estimated_cost(client: AsyncClient, db_session: AsyncSession, requester: User):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = UUID((await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("40.00"))
    db_session.add(item)
    refund = (await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))).scalar_one()
    refund.total_requested_amount = Decimal("40.00")
    await db_session.commit()

    response = await client.patch(f"/api/v1/refunds/{refund_id}/items/{item.id}", json={"requestedAmount": "260.00"})
    assert response.status_code == 400

    await db_session.refresh(refund)
    assert refund.total_requested_amount == Decimal("40.00")


@pytest.mark.asyncio
async def test_approve_refund_charges_reimbursed_and_returns_rest_to_fund(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission, fund = await create_funded_mission(db_session, requester)
    refund, item = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: admin_user
    response = await client.patch(f"/api/v1/refunds/{refund.id}/approve", json=approve_payload(item.id))
    assert response.status_code == 200

    # Riservati 250, rimborsati 20: il fondo paga 20 e gli tornano disponibili 230.
    await db_session.refresh(fund)
    assert fund.amount == Decimal("980.00")
    assert fund.committed_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_approve_refund_fails_when_reimbursed_exceeds_requested(client: AsyncClient, db_session: AsyncSession, requester: User, admin_user: User):
    mission, fund = await create_funded_mission(db_session, requester)
    refund, item = await create_submitted_refund(db_session, mission.id)

    app.dependency_overrides[current_active_user] = lambda: admin_user
    payload = {"items": [{"itemId": str(item.id), "reimbursedAmount": "30.00"}]}
    response = await client.patch(f"/api/v1/refunds/{refund.id}/approve", json=payload)
    assert response.status_code == 400

    await db_session.refresh(fund)
    await db_session.refresh(refund)
    assert fund.amount == Decimal("1000.00")
    assert fund.committed_amount == Decimal("250.00")
    assert refund.status == RefundStatus.SUBMITTED


def _make_jpeg_bytes(width: int = 200, height: int = 120) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(240, 240, 240)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_submit_blocked_while_item_needs_review_and_unlocked_after_update(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    create_resp = await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})
    refund_id = UUID(create_resp.json()["id"])

    item = _make_test_item(refund_id, requester.id, Decimal("30.00"), needs_review=True)
    db_session.add(item)
    await db_session.flush()
    item_id = item.id

    refund = (await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))).scalar_one()
    refund.total_requested_amount = Decimal("30.00")
    await db_session.commit()

    blocked_resp = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert blocked_resp.status_code == 400
    assert "pending review" in blocked_resp.json()["message"].lower()

    await db_session.refresh(requester)

    patch_resp = await client.patch(
        f"/api/v1/refunds/{refund_id}/items/{item_id}",
        json={"description": "Spesa verificata"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["needsReview"] is False

    submit_resp = await client.patch(f"/api/v1/refunds/{refund_id}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_detect_receipt_boxes_happy_path_image(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    mock_detector = MagicMock()
    mock_detector.detect = AsyncMock(
        return_value=ReceiptDetectionResponseDTO(
            image_width=200,
            image_height=120,
            boxes=[
                BoundingBoxDTO(x=10, y=10, width=80, height=100, page=0),
                BoundingBoxDTO(x=105, y=10, width=85, height=100, page=0),
            ],
            pages=[],
        )
    )

    ai_service = ReceiptAIService(currency_service=CurrencyConversionService())
    ai_service.detector = mock_detector
    app.dependency_overrides[get_receipt_ai_service] = lambda: ai_service

    try:
        files = {"file": ("multi.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
        response = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect", files=files)
    finally:
        app.dependency_overrides.pop(get_receipt_ai_service, None)

    assert response.status_code == 200
    data = response.json()
    assert data["imageWidth"] == 200
    assert data["imageHeight"] == 120
    assert len(data["boxes"]) == 2
    assert data["boxes"][0]["x"] == 10
    assert data["pages"] == []


@pytest.mark.asyncio
async def test_detect_receipt_boxes_happy_path_multipage_pdf(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    page_1 = _make_jpeg_bytes(300, 400)
    page_2 = _make_jpeg_bytes(300, 400)

    mock_detector = MagicMock()
    mock_detector.detect = AsyncMock(
        side_effect=[
            ReceiptDetectionResponseDTO(
                image_width=300,
                image_height=400,
                boxes=[BoundingBoxDTO(x=20, y=20, width=200, height=300, page=0)],
            ),
            ReceiptDetectionResponseDTO(
                image_width=300,
                image_height=400,
                boxes=[BoundingBoxDTO(x=30, y=40, width=210, height=310, page=0)],
            ),
        ]
    )

    with (
        patch("app.services.receipt_ai_service.get_receipt_detector", return_value=mock_detector),
        patch("app.services.receipt_ai_service.render_pdf_pages", return_value=[page_1, page_2]),
    ):
        files = {"file": ("scontrini.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
        response = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect", files=files)

    assert response.status_code == 200
    data = response.json()
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page"] == 0
    assert data["pages"][1]["page"] == 1
    assert data["pages"][0]["imageDataUrl"].startswith("data:image/jpeg;base64,")
    assert [b["page"] for b in data["boxes"]] == [0, 1]


@pytest.mark.asyncio
async def test_detect_receipt_boxes_validation_missing_file(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    response = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_detect_receipt_boxes_security_unauthorized_and_forbidden(
    client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    app.dependency_overrides.pop(current_active_user, None)
    files_unauth = {"file": ("multi.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_401 = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect", files=files_unauth)
    assert resp_401.status_code == 401

    app.dependency_overrides[current_active_user] = lambda: other_user
    files_forbidden = {"file": ("multi.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_403 = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect", files=files_forbidden)
    assert resp_403.status_code == 403


@pytest.mark.asyncio
async def test_detect_receipt_boxes_rejects_unsupported_and_empty_files(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    bad_files = {"file": ("script.exe", io.BytesIO(b"MZ..."), "application/octet-stream")}
    resp_415 = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect", files=bad_files)
    assert resp_415.status_code == 415

    empty_files = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
    resp_400 = await client.post(f"/api/v1/refunds/{refund_id}/receipts/detect", files=empty_files)
    assert resp_400.status_code == 400


@pytest.mark.asyncio
async def test_batch_process_receipts_happy_path_and_inconsistent_fallback(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = UUID((await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"])

    ollama_outputs = [
        {
            "category": "MEALS",
            "subtype": "MEALS_EXPENSE",
            "amount": 18.50,
            "currency": "EUR",
            "starts_at": "2026-11-20T13:00",
            "merchant": "Trattoria Roma",
            "description": "Lunch in Rome",
        },
        {
            "category": "TRANSPORT",
            "subtype": "TRAIN",
            "amount": None,
            "currency": "EUR",
            "itinerary_from": None,
            "itinerary_to": None,
            "description": "",
        },
    ]

    boxes_payload = json.dumps([
        {"x": 5, "y": 5, "width": 80, "height": 100, "page": 0},
        {"x": 100, "y": 5, "width": 90, "height": 100, "page": 0},
    ])

    with (
        patch("app.services.refund_service.minio_client") as mock_minio,
        patch("app.services.receipt_ai_service.ReceiptAIService._sync_ocr", return_value=("OCR TEXT", ["OCR TEXT"], 0.9)),
        patch("app.services.receipt_ai_service.ReceiptAIService._query_ollama", new=AsyncMock(side_effect=ollama_outputs)),
    ):
        mock_minio.put_object.return_value = None
        files = {"file": ("batch_tickets.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
        response = await client.post(
            f"/api/v1/refunds/{refund_id}/receipts/batch-process",
            files=files,
            data={"boxes": boxes_payload},
        )

    assert response.status_code == 201
    items = response.json()
    assert len(items) == 2

    assert items[0]["category"] == "MEALS"
    assert items[0]["requestedAmount"] == "18.50"
    assert items[0]["needsReview"] is True

    assert items[1]["category"] == "OTHER"
    assert items[1]["subtype"] is None
    assert items[1]["requestedAmount"] == "0.01"
    assert items[1]["description"] == "Pending review"
    assert items[1]["needsReview"] is True

    assert mock_minio.put_object.call_count == 2
    refund = (await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))).scalar_one()
    assert refund.total_requested_amount == Decimal("18.51")


@pytest.mark.asyncio
async def test_batch_process_receipts_validation_errors(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]

    files_1 = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_invalid_json = await client.post(
        f"/api/v1/refunds/{refund_id}/receipts/batch-process",
        files=files_1,
        data={"boxes": "{not-valid-json"},
    )
    assert resp_invalid_json.status_code == 422

    files_2 = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_invalid_box = await client.post(
        f"/api/v1/refunds/{refund_id}/receipts/batch-process",
        files=files_2,
        data={"boxes": json.dumps([{"x": -5, "y": 0, "width": 0, "height": 50}])},
    )
    assert resp_invalid_box.status_code == 422


@pytest.mark.asyncio
async def test_batch_process_receipts_security_unauthorized_and_forbidden(
    client: AsyncClient, db_session: AsyncSession, requester: User, other_user: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = (await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"]
    boxes_payload = json.dumps([{"x": 10, "y": 10, "width": 50, "height": 50, "page": 0}])

    app.dependency_overrides.pop(current_active_user, None)
    files_401 = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_401 = await client.post(
        f"/api/v1/refunds/{refund_id}/receipts/batch-process",
        files=files_401,
        data={"boxes": boxes_payload},
    )
    assert resp_401.status_code == 401

    app.dependency_overrides[current_active_user] = lambda: other_user
    files_403 = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_403 = await client.post(
        f"/api/v1/refunds/{refund_id}/receipts/batch-process",
        files=files_403,
        data={"boxes": boxes_payload},
    )
    assert resp_403.status_code == 403


@pytest.mark.asyncio
async def test_batch_process_receipts_business_errors(
    client: AsyncClient, db_session: AsyncSession, requester: User
):
    mission = await create_mission(db_session, requester.id, ended=True)
    refund_id = UUID((await client.post("/api/v1/refunds", json={"missionId": str(mission.id)})).json()["id"])

    files_empty_boxes = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_empty = await client.post(
        f"/api/v1/refunds/{refund_id}/receipts/batch-process",
        files=files_empty_boxes,
        data={"boxes": "[]"},
    )
    assert resp_empty.status_code == 400

    files_404 = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_404 = await client.post(
        f"/api/v1/refunds/{uuid4()}/receipts/batch-process",
        files=files_404,
        data={"boxes": json.dumps([{"x": 10, "y": 10, "width": 50, "height": 50}])},
    )
    assert resp_404.status_code == 404

    with patch("app.services.receipt_ai_service.render_pdf_pages", return_value=[_make_jpeg_bytes()]):
        files_pdf = {"file": ("one_page.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
        resp_bad_page = await client.post(
            f"/api/v1/refunds/{refund_id}/receipts/batch-process",
            files=files_pdf,
            data={"boxes": json.dumps([{"x": 10, "y": 10, "width": 50, "height": 50, "page": 3}])},
        )
    assert resp_bad_page.status_code == 400

    refund = (await db_session.execute(select(RefundRequest).where(RefundRequest.id == refund_id))).scalar_one()
    refund.status = RefundStatus.SUBMITTED
    await db_session.commit()

    files_submitted = {"file": ("batch.jpg", io.BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp_submitted = await client.post(
        f"/api/v1/refunds/{refund_id}/receipts/batch-process",
        files=files_submitted,
        data={"boxes": json.dumps([{"x": 10, "y": 10, "width": 50, "height": 50}])},
    )
    assert resp_submitted.status_code == 400