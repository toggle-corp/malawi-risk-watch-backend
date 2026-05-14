import strawberry
import strawberry_django
from django.db.models import Q

from apps.admin_areas.models import AdminArea


@strawberry_django.filters.filter(AdminArea, lookups=True)
class AdminAreaFilter:
    id: strawberry.ID | None = strawberry.UNSET
    level: int | None = strawberry.UNSET
    parent_id: strawberry.ID | None = strawberry.UNSET

    @strawberry_django.filter_field
    def search(self, value: str, prefix: str) -> Q:
        return Q(name__icontains=value)
