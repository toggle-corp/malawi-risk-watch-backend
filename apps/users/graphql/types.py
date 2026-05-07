import strawberry
import strawberry_django

from apps.users.models import User


@strawberry_django.type(User)
class UserType:
    id: strawberry.ID
    email: strawberry.auto
    name: strawberry.auto
    role: strawberry.auto
    is_active: strawberry.auto
    created_at: strawberry.auto
