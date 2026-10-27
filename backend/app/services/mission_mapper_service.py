from app.db.mission import Mission
from app.schemas.mission import MissionCreateDTO, MissionDTO, MissionUpdateDTO



class MissionMapperService:
    @staticmethod
    def convert_to_dto(mission: Mission) -> MissionDTO:
        return MissionDTO.model_validate(mission)

    @staticmethod
    def convert_to_entity(data: MissionCreateDTO) -> Mission:
        return Mission(**data.model_dump())

    @staticmethod
    def update_entity(mission: Mission, data: MissionUpdateDTO) -> None:
        for field, value in data.model_dump().items():
            setattr(mission, field, value)
