import strawberry
import strawberry_django

from apps.admin_areas.models import AdminArea


@strawberry_django.order_type(AdminArea)
class AdminAreaOrder:
    level: strawberry.auto
    name: strawberry.auto
