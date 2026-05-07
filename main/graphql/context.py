from dataclasses import dataclass

from strawberry.django.context import StrawberryDjangoContext
from strawberry.types import Info as _Info


@dataclass
class GraphQLContext(StrawberryDjangoContext): ...


class Info(_Info):
    context: GraphQLContext  # type: ignore[reportIncompatibleMethodOverride]
