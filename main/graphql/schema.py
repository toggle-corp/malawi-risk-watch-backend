import strawberry
from asgiref.sync import sync_to_async
from strawberry.django.views import AsyncGraphQLView
from strawberry_django.optimizer import DjangoOptimizerExtension

from apps.admin_areas.graphql import queries as admin_area_queries
from apps.pipeline.graphql import mutations as pipeline_mutations
from apps.pipeline.graphql import queries as pipeline_queries
from apps.users.graphql import queries as user_queries

from .context import GraphQLContext
from .enums import AppEnumCollection, AppEnumCollectionData


class CustomAsyncGraphQLView(AsyncGraphQLView):
    async def get_context(self, *args, **kwargs) -> GraphQLContext:  # type: ignore[reportIncompatibleMethodOverride]
        context = GraphQLContext(*args, **kwargs)
        # Pre-resolve the lazy request.user in a worker thread so sync permission
        # classes (required by OffsetPaginated) can safely access user attributes.
        await sync_to_async(lambda: context.request.user.is_authenticated)()
        return context


@strawberry.type
class Query(
    user_queries.Query,
    admin_area_queries.Query,
    pipeline_queries.Query,
):
    enums: AppEnumCollection = strawberry.field(  # type: ignore[reportGeneralTypeIssues]
        resolver=lambda: AppEnumCollectionData(),  # noqa: PLW0108
    )


@strawberry.type
class Mutation(
    pipeline_mutations.Mutation,
):
    pass


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
    ],
)
