import strawberry
import strawberry_django
from strawberry_django.pagination import OffsetPaginated

from .types import UserType


@strawberry.type
class Query:
    users: OffsetPaginated[UserType] = strawberry_django.offset_paginated()
    user: UserType = strawberry_django.field()
