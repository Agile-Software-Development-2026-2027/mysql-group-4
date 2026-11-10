from uuid import UUID


class ResourceNotFoundError(LookupError):
    def __init__(self, resource: str, resource_id: UUID):
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} not found")


class MissionNotFoundError(ResourceNotFoundError):
    def __init__(self, mission_id: UUID):
        self.mission_id = mission_id
        super().__init__("Mission", mission_id)


class FundNotFoundError(ResourceNotFoundError):
    def __init__(self, fund_id: UUID):
        self.fund_id = fund_id
        super().__init__("Fund", fund_id)


class UserNotFoundError(ResourceNotFoundError):
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        super().__init__("User", user_id)


class RefundNotFoundError(ResourceNotFoundError):
    def __init__(self, refund_id: UUID):
        self.refund_id = refund_id
        super().__init__("RefundRequest", refund_id)


class AccessDeniedError(PermissionError):
    pass


class InvalidMissionStateError(ValueError):
    pass


class InvalidMissionPeriodError(ValueError):
    pass


class InvalidRefundRequestDateError(InvalidMissionPeriodError):
    pass


class InvalidRefundStateError(ValueError):
    pass


class InvalidRefundDecisionError(ValueError):
    pass


class FundLockedError(Exception):
    def __init__(self, fund_id: UUID):
        self.fund_id = fund_id
        super().__init__(f"Fund {fund_id} is already used by another mission")
