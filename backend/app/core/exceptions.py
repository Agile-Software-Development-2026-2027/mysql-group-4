from uuid import UUID


class ResourceNotFoundError(LookupError):
    def __init__(self, resource: str, resource_id: UUID):
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id} not found")


class MissionNotFoundError(ResourceNotFoundError):
    def __init__(self, mission_id: UUID):
        self.mission_id = mission_id
        super().__init__("Mission", mission_id)


class UserNotFoundError(ResourceNotFoundError):
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        super().__init__("User", user_id)


class AccessDeniedError(PermissionError):
    pass


class InvalidMissionStateError(ValueError):
    pass


class InvalidMissionPeriodError(ValueError):
    pass
