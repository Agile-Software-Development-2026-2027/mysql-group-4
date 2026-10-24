from enum import Enum

class EmploymentLevel(str, Enum):
    RICERCATORE = "ricercatore"
    PROFESSORE_ORDINARIO = "professore_ordinario"
    PROFESSORE_ASSOCIATO = "professore_associato"
