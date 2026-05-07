from app.domain.entities.agreement import Category


class CategoryBuilder:
    def build(self, raw: dict) -> list[Category]:
        categories = []
        for category in raw.get("raw_categories") or []:
            categories.append(Category(
                category_id=str(category.get("category_id") or category.get("code") or category.get("name") or "A"),
                name=category.get("name") or category.get("category_id") or "Categoria",
                basic_salary=float(category.get("basic_salary") or category.get("base_salary") or 0),
            ))
        return categories
