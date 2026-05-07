from enum import StrEnum


class EventType(StrEnum):
    ABSENCE = "ABSENCE"
    OVERTIME = "OVERTIME"
    BONUS = "BONUS"
    LEAVE = "LEAVE"
    HOLIDAY_WORKED = "HOLIDAY_WORKED"
