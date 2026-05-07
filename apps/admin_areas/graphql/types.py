import strawberry
import strawberry_django

from apps.admin_areas.models import AdminArea


@strawberry_django.type(AdminArea)
class AdminAreaType:
    id: strawberry.ID
    admin_code: strawberry.auto
    name: strawberry.auto
    level: strawberry.auto
    parent_id: strawberry.ID | None
    country_iso: strawberry.auto
    created_at: strawberry.auto
