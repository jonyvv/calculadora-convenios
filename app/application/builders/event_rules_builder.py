from app.domain.entities.agreement import EventRule


class EventRulesBuilder:
    def build(self, raw: dict) -> list[EventRule]:
        rules = []
        for rule in raw.get("raw_event_rules") or []:
            rules.append(EventRule(
                event_type=rule.get("event_type") or rule.get("type") or "UNKNOWN",
                subtype=rule.get("subtype"),
                effects=rule.get("effects") or [],
            ))
        return rules
