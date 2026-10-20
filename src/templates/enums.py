from enum import StrEnum


class FieldType(StrEnum):
    TEXT = "text"
    CODE = "code"
    NUMBER = "number"
    WEIGHT = "weight"
    CURRENCY = "currency"
    DATE = "date"
    PARTY = "party"
