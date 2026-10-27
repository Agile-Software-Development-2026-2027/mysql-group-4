from enum import Enum


class EmploymentLevel(str, Enum):
    RICERCATORE = "ricercatore"
    PROFESSORE_ORDINARIO = "professore_ordinario"
    PROFESSORE_ASSOCIATO = "professore_associato"


class MissionStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MissionType(str, Enum):
    RESEARCH = "RESEARCH"
    TRAINING = "TRAINING"
    TEACHING = "TEACHING"
