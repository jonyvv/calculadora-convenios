from app.domain.entities.agreement import Category


class CategoryBuilder:
    def build(self, raw: dict) -> list[Category]:
        categories = []
        seen = set()
        for category in raw.get("raw_categories") or []:
            zone = (
                category.get("zone")
                or category.get("zona_geografica")
                or category.get("location")
                or category.get("ubicacion")
                or category.get("region")
                or category.get("provincia")
            )
            base_id = str(category.get("category_id") or category.get("code") or category.get("name") or "A")
            category_id = self._category_id_with_zone(base_id, zone)
            category_id = self._unique_category_id(category_id, seen)
            seen.add(category_id)
            categories.append(Category(
                category_id=category_id,
                name=category.get("name") or category.get("category_id") or "Categoria",
                basic_salary=float(category.get("basic_salary") or category.get("base_salary") or 0),
                zone=zone,
                location=zone,
            ))
        return categories

    def _category_id_with_zone(self, category_id: str, zone: str | None) -> str:
        if not zone:
            return str(category_id)
        suffix = "".join(character if character.isalnum() else "_" for character in str(zone).upper()).strip("_")[:24]
        normalized_id = "".join(character if character.isalnum() else "_" for character in str(category_id).upper()).strip("_")
        if not suffix or suffix in normalized_id:
            return str(category_id)
        return f"{category_id}_{suffix}"

    def _unique_category_id(self, category_id: str, seen: set[str]) -> str:
        if category_id not in seen:
            return category_id
        index = 2
        while f"{category_id}_{index}" in seen:
            index += 1
        return f"{category_id}_{index}"
