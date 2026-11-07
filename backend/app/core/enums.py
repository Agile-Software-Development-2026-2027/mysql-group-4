from enum import Enum


class EmploymentLevel(str, Enum):
    RICERCATORE = "ricercatore"
    PROFESSORE_ORDINARIO = "professore_ordinario"
    PROFESSORE_ASSOCIATO = "professore_associato"


class MissionStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class MissionType(str, Enum):
    RESEARCH = "RESEARCH"
    TRAINING = "TRAINING"
    TEACHING = "TEACHING"


class RefundStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"


class ExpenseCategory(str, Enum):
    TRANSPORT = "TRANSPORT"
    ACCOMMODATION = "ACCOMMODATION"
    MEALS = "MEALS"
    OTHER = "OTHER"


class ExpenseSubtype(str, Enum):
    # Trasporto
    TRAIN = "TRAIN"
    PLANE = "PLANE"
    SHIP = "SHIP"
    PUBLIC_TRANSPORT = "PUBLIC_TRANSPORT"
    TAXI_RENTAL = "TAXI_RENTAL"
    OWN_VEHICLE = "OWN_VEHICLE"
    # Alloggio
    ACCOMMODATION_EXPENSE = "ACCOMMODATION_EXPENSE"
    OTHER_ACCOMMODATION_EXPENSE = "OTHER_ACCOMMODATION_EXPENSE"
    # Vitto
    MEALS_EXPENSE = "MEALS_EXPENSE"
    OTHER_MEALS_EXPENSE = "OTHER_MEALS_EXPENSE"

