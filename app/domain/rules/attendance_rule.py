from app.domain.entities.agreement import Agreement
from app.domain.entities.monthly_event import Event


def loses_attendance_bonus(agreement: Agreement, events: list[Event]) -> bool:
    for event in events:
        for rule in agreement.event_rules:
            same_type = rule.event_type == event.type
            same_subtype = rule.subtype is None or rule.subtype == event.subtype
            if same_type and same_subtype and "LOSE_ATTENDANCE" in rule.effects:
                return True
    return False
