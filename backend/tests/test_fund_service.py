import pytest
from datetime import datetime
from types import SimpleNamespace
from decimal import Decimal
from uuid import uuid4
from unittest.mock import create_autospec, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.enums import MissionStatus, RefundStatus
from app.core.exceptions import AccessDeniedError, FundAmountError, FundInUseError, FundNotFoundError
from app.crud.fund_repository import FundRepository
from app.crud.user_repository import UserRepository
from app.schemas.fund import FundCreateDTO, FundDTO, FundUpdateDTO
from app.schemas.page import Page, PageRequest
from app.services.fund_service import FundService
from tests.factories import make_fund, make_user, make_mission


class TestFundService:

    @pytest.fixture(autouse=True)
    def setup_dependencies(self):
        self.user = make_user(fiscal_code="RSSMRA80A01H501U")
        self.other = make_user(fiscal_code="VRDLGI85B02F205X")
        self.fund = make_fund(responsible_fc=self.user.fiscal_code)
        self.session = create_autospec(AsyncSession, instance=True)
        self.repository = create_autospec(FundRepository, instance=True)
        self.user_repository = create_autospec(UserRepository, instance=True)
        self.user_repository.get_user_by_id.side_effect = lambda session, user_id: {
            self.user.id: self.user,
            self.other.id: self.other,
        }.get(user_id)
        self.repository.find_by_id.return_value = self.fund
        self.repository.find_by_id_for_update.return_value = self.fund
        self.repository.find_funded_missions.return_value = {}
        self.repository.is_funding_missions.return_value = False

        def fake_save(f):
            if f.id is None:
                f.id = self.fund.id
                f.committed_amount = Decimal("0.0")
            return f

        self.repository.save.side_effect = fake_save
        self.service = FundService(self.session, self.repository, self.user_repository)

    async def test_create_assigns_authenticated_user_as_responsible(self):
        data = FundCreateDTO(name="New fund", amount=Decimal("100.00"))
        result = await self.service.create_fund(data, self.user.id)
        saved = self.repository.save.await_args.args[0]
        assert saved.responsible_fc == self.user.fiscal_code
        assert saved.created_by == self.user.id
        assert result.responsible_fc == self.user.fiscal_code
        self.session.commit.assert_awaited_once()

    async def test_get_by_id_returns_own_fund(self):
        result = await self.service.get_fund_by_id(self.fund.id, self.user.id)
        assert result == FundDTO.model_validate(self.fund)

    @pytest.mark.parametrize(
        ("refund_status", "expected"),
        [(None, None), (RefundStatus.SUBMITTED, None), (RefundStatus.APPROVED, Decimal("80.00"))],
    )
    async def test_get_by_id_shows_refund_amount_only_when_approved(self, refund_status, expected):
        row = SimpleNamespace(
            id=uuid4(), subject="Convegno", status=MissionStatus.ACCEPTED,
            estimated_cost=Decimal("100.00"), name="Mario", surname="Rossi",
            created_at=datetime(2026, 10, 24), refund_status=refund_status,
            total_reimbursed_amount=Decimal("80.00"),
        )
        self.repository.find_funded_missions.return_value = {self.fund.id: [row]}
        result = await self.service.get_fund_by_id(self.fund.id, self.user.id)
        assert result.missions[0].refund_amount == expected

    async def test_get_by_id_forbids_other_users(self):
        with pytest.raises(AccessDeniedError):
            await self.service.get_fund_by_id(self.fund.id, self.other.id)

    async def test_get_by_id_allows_superuser(self):
        admin = make_user(fiscal_code="BNCLRA90C03L219Y", is_superuser=True)
        self.user_repository.get_user_by_id.side_effect = lambda session, user_id: admin
        await self.service.get_fund_by_id(self.fund.id, admin.id)

    async def test_get_by_id_missing_fund_raises_not_found(self):
        self.repository.find_by_id.return_value = None
        with pytest.raises(FundNotFoundError):
            await self.service.get_fund_by_id(self.fund.id, self.user.id)

    async def test_get_fund_by_mission_id_success(self):
        mission = make_mission(requester_id=self.user.id, fund_id=self.fund.id)
        self.session.scalar = AsyncMock(return_value=mission)
        result = await self.service.get_fund_by_mission_id(mission.id, self.user.id)
        assert result.id == self.fund.id
        self.repository.find_by_id.assert_awaited_once_with(self.fund.id)

    @pytest.mark.parametrize("mission_exists", (False, True))
    async def test_get_fund_by_mission_id_without_fund_returns_none(self, mission_exists):
        mission = make_mission(requester_id=self.user.id) if mission_exists else None
        self.session.scalar = AsyncMock(return_value=mission)
        assert await self.service.get_fund_by_mission_id(uuid4(), self.user.id) is None
        self.repository.find_by_id.assert_not_awaited()

    async def test_get_fund_by_mission_id_unauthorized(self):
        foreign_fund = make_fund(responsible_fc="OTHERFC90A01H501Z")
        mission = make_mission(fund_id=foreign_fund.id)
        self.repository.find_by_id.return_value = foreign_fund
        self.session.scalar = AsyncMock(return_value=mission)
        with pytest.raises(AccessDeniedError):
            await self.service.get_fund_by_mission_id(mission.id, self.other.id)

    async def test_listing_is_scoped_to_responsible(self):
        request = PageRequest(page=1, size=5)
        self.repository.find_all.return_value = Page(content=[self.fund], total_elements=6, number=1, size=5)
        result = await self.service.get_funds(self.user.id, request)
        self.repository.find_all.assert_awaited_once_with(
            responsible_fc=self.user.fiscal_code, page_request=request
        )
        assert result.content == [FundDTO.model_validate(self.fund)]
        assert result.total_elements == 6

    async def test_update_changes_fields_and_audit(self):
        data = FundUpdateDTO(name="Renamed", amount=Decimal("42.00"))
        result = await self.service.update_fund(self.fund.id, data, self.user.id)
        assert result.name == "Renamed"
        assert result.amount == Decimal("42.00")
        assert self.fund.updated_by == self.user.id
        self.session.commit.assert_awaited_once()

    async def test_update_rejects_amount_below_committed(self):
        self.fund.committed_amount = Decimal("800.00")
        data = FundUpdateDTO(name="Research fund", amount=Decimal("500.00"))
        with pytest.raises(FundAmountError, match=r"€ 800\.00 committed .* cannot be lowered to € 500\.00"):
            await self.service.update_fund(self.fund.id, data, self.user.id)
        assert self.fund.amount == Decimal("5000.00")
        self.repository.save.assert_not_awaited()
        self.session.rollback.assert_awaited_once()

    async def test_update_allows_amount_equal_to_committed(self):
        self.fund.committed_amount = Decimal("800.00")
        data = FundUpdateDTO(name="Research fund", amount=Decimal("800.00"))
        result = await self.service.update_fund(self.fund.id, data, self.user.id)
        assert result.amount == Decimal("800.00")
        assert result.remaining_amount == Decimal("0.00")
        self.session.commit.assert_awaited_once()

    @pytest.mark.parametrize("action", ("update", "delete"))
    async def test_only_responsible_can_change_fund(self, action):
        with pytest.raises(AccessDeniedError):
            if action == "update":
                await self.service.update_fund(self.fund.id, FundUpdateDTO(name="x", amount=Decimal("1")), self.other.id)
            else:
                await self.service.delete_fund(self.fund.id, self.other.id)
        self.session.rollback.assert_awaited_once()
        self.repository.save.assert_not_awaited()
        self.repository.delete.assert_not_awaited()

    async def test_delete_removes_own_fund(self):
        await self.service.delete_fund(self.fund.id, self.user.id)
        self.repository.delete.assert_awaited_once_with(self.fund)

    async def test_delete_of_a_fund_in_use_requires_force(self):
        self.repository.is_funding_missions.return_value = True
        with pytest.raises(FundInUseError):
            await self.service.delete_fund(self.fund.id, self.user.id)
        self.repository.delete.assert_not_awaited()

        await self.service.delete_fund(self.fund.id, self.user.id, force=True)
        self.repository.delete.assert_awaited_once_with(self.fund)
        self.session.commit.assert_awaited_once()


class TestFundSchema:

    def test_rejects_negative_amount(self):
        with pytest.raises(ValueError):
            FundCreateDTO(name="Fund", amount=Decimal("-1"))

    def test_rejects_responsible_in_body(self):
        with pytest.raises(ValueError):
            FundCreateDTO(name="Fund", amount=Decimal("1"), responsibleFc="RSSMRA80A01H501U")