from datetime import datetime
from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ExpenseCategory, ExpenseSubtype, RefundStatus
from app.db import RefundItem, RefundRequest
from tests.factories import make_mission, make_user


@pytest.mark.asyncio
async def test_create_refund_request_and_transport_item(db_session: AsyncSession):
    user = make_user(
        email="test@unical.it",
        fiscal_code="RSSMRA80A01H501U",
        name="Mario",
        surname="Rossi",
        department="DICES",
        employment_level="ricercatore",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(
        mission_id=mission.id,
        status=RefundStatus.DRAFT,
        total_requested_amount=Decimal("45.50"),
        total_reimbursed_amount=Decimal("0.00"),
    )
    db_session.add(refund_request)
    await db_session.flush()

    item = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.TRANSPORT,
        subtype=ExpenseSubtype.TRAIN,
        itinerary_from="Paola",
        itinerary_to="Roma Termini",
        starts_at=datetime(2026, 11, 1, 8, 30),
        ends_at=datetime(2026, 11, 1, 12, 15),
        requested_amount=Decimal("45.50"),
        currency="EUR",
        is_traceable=True,
        receipt_file_path="missions/123/receipt.pdf",
        receipt_original_filename="biglietto_treno.pdf",
        description="Frecciarossa andata",
    )
    db_session.add(item)
    await db_session.commit()

    result = await db_session.execute(
        select(RefundRequest).where(RefundRequest.id == refund_request.id)
    )
    loaded_req = result.scalar_one()
    assert loaded_req.mission_id == mission.id
    assert loaded_req.status == RefundStatus.DRAFT
    assert loaded_req.total_requested_amount == Decimal("45.50")

    result_items = await db_session.execute(
        select(RefundItem).where(RefundItem.refund_request_id == refund_request.id)
    )
    loaded_items = result_items.scalars().all()
    assert len(loaded_items) == 1
    assert loaded_items[0].category == ExpenseCategory.TRANSPORT
    assert loaded_items[0].subtype == ExpenseSubtype.TRAIN
    assert loaded_items[0].itinerary_from == "Paola"
    assert loaded_items[0].itinerary_to == "Roma Termini"


@pytest.mark.asyncio
async def test_meals_item_valid_without_itinerary_or_ends_at(db_session: AsyncSession):
    user = make_user(
        email="test2@unical.it",
        fiscal_code="BNCMRA80A01H501U",
        name="Marco",
        surname="Bianchi",
        department="DEMACS",
        employment_level="professore_associato",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    meal_item = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        itinerary_from=None,
        itinerary_to=None,
        starts_at=datetime(2026, 11, 1, 13, 0),
        ends_at=None,
        requested_amount=Decimal("25.00"),
        receipt_file_path="missions/123/meal.pdf",
        receipt_original_filename="scontrino.pdf",
        description="Pranzo di lavoro",
    )
    db_session.add(meal_item)
    await db_session.commit()

    res = await db_session.execute(select(RefundItem).where(RefundItem.id == meal_item.id))
    saved = res.scalar_one()
    assert saved.category == ExpenseCategory.MEALS
    assert saved.ends_at is None
    assert saved.itinerary_from is None


@pytest.mark.asyncio
async def test_meals_item_rejected_if_has_itinerary(db_session: AsyncSession):
    user = make_user(
        email="test3@unical.it",
        fiscal_code="VRDMRA80A01H501U",
        name="Giuseppe",
        surname="Verdi",
        department="DISPES",
        employment_level="professore_ordinario",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    invalid_meal = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        itinerary_from="Roma",
        itinerary_to="Milano",
        starts_at=datetime(2026, 11, 1, 13, 0),
        ends_at=None,
        requested_amount=Decimal("30.00"),
        receipt_file_path="missions/123/meal.pdf",
        receipt_original_filename="scontrino.pdf",
        description="Pranzo",
    )
    db_session.add(invalid_meal)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_transport_rejected_without_itinerary(db_session: AsyncSession):
    user = make_user(
        email="test4@unical.it",
        fiscal_code="NERMRA80A01H501U",
        name="Antonio",
        surname="Neri",
        department="DICES",
        employment_level="ricercatore",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    invalid_transport = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.TRANSPORT,
        subtype=ExpenseSubtype.TRAIN,
        itinerary_from=None,
        itinerary_to=None,
        starts_at=datetime(2026, 11, 1, 8, 0),
        ends_at=datetime(2026, 11, 1, 12, 0),
        requested_amount=Decimal("50.00"),
        receipt_file_path="missions/123/train.pdf",
        receipt_original_filename="train.pdf",
        description="Treno",
    )
    db_session.add(invalid_transport)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_negative_requested_amount_rejected(db_session: AsyncSession):
    user = make_user(
        email="test5@unical.it",
        fiscal_code="GLLMRA80A01H501U",
        name="Luigi",
        surname="Gialli",
        department="DICES",
        employment_level="ricercatore",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    invalid_amount = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=datetime(2026, 11, 1, 13, 0),
        ends_at=None,
        requested_amount=Decimal("-10.00"),  # Negative amount!
        receipt_file_path="missions/123/meal.pdf",
        receipt_original_filename="scontrino.pdf",
        description="Pranzo",
    )
    db_session.add(invalid_amount)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_exceeded_maximum_requested_amount_rejected(db_session: AsyncSession):
    user = make_user(
        email="test_max@unical.it",
        fiscal_code="MAXMRA80A01H501U",
        name="Massimo",
        surname="Verdi",
        department="DICES",
        employment_level="ricercatore",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    invalid_max = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=datetime(2026, 11, 1, 13, 0),
        ends_at=None,
        requested_amount=Decimal("10000.01"),  # Exceeds max 10000.00!
        receipt_file_path="missions/123/meal.pdf",
        receipt_original_filename="scontrino.pdf",
        description="Pranzo da 10000.01",
    )
    db_session.add(invalid_max)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_reimbursed_amount_cannot_exceed_requested_amount(db_session: AsyncSession):
    user = make_user(
        email="test6@unical.it",
        fiscal_code="BLUMRA80A01H501U",
        name="Franco",
        surname="Blu",
        department="DICES",
        employment_level="ricercatore",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    exceeded_reimbursed = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.MEALS,
        subtype=ExpenseSubtype.MEALS_EXPENSE,
        starts_at=datetime(2026, 11, 1, 13, 0),
        ends_at=None,
        requested_amount=Decimal("30.00"),
        reimbursed_amount=Decimal("35.00"),
        receipt_file_path="missions/123/meal.pdf",
        receipt_original_filename="scontrino.pdf",
        description="Pranzo",
    )
    db_session.add(exceeded_reimbursed)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_other_category_requires_null_subtype_in_db(db_session: AsyncSession):
    user = make_user(
        email="test_other@unical.it",
        fiscal_code="OTRMRA80A01H501U",
        name="Other",
        surname="User",
        department="DICES",
        employment_level="ricercatore",
    )
    db_session.add(user)
    await db_session.flush()

    mission = make_mission(requester_id=user.id, fund_manager_id=user.id)
    db_session.add(mission)
    await db_session.flush()

    refund_request = RefundRequest(mission_id=mission.id)
    db_session.add(refund_request)
    await db_session.flush()

    # Valido: category=OTHER e subtype=None
    valid_other = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.OTHER,
        subtype=None,
        starts_at=datetime(2026, 11, 1, 10, 0),
        ends_at=None,
        requested_amount=Decimal("120.00"),
        receipt_file_path="missions/123/fee.pdf",
        receipt_original_filename="iscrizione.pdf",
        description="Quota iscrizione congresso",
    )
    db_session.add(valid_other)
    await db_session.commit()

    # Non valido: category=OTHER ma con subtype valorizzato
    invalid_other = RefundItem(
        refund_request_id=refund_request.id,
        category=ExpenseCategory.OTHER,
        subtype=ExpenseSubtype.TRAIN,
        starts_at=datetime(2026, 11, 1, 10, 0),
        ends_at=None,
        requested_amount=Decimal("50.00"),
        receipt_file_path="missions/123/err.pdf",
        receipt_original_filename="err.pdf",
        description="Errore subtype su OTHER",
    )
    db_session.add(invalid_other)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
