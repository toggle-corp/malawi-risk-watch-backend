from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from health_check.views import HealthCheckView

from main.graphql.schema import CustomAsyncGraphQLView
from main.graphql.schema import schema as graphql_schema

admin.site.site_header = "MRCS DRM Admin"

base_graphql_kwargs = dict(
    schema=graphql_schema,
    multipart_uploads_enabled=True,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "health-check/",
        HealthCheckView.as_view(
            checks=[
                "health_check.Cache",
                "health_check.Database",
                "health_check.Mail",
                "health_check.Storage",
                "health_check.contrib.psutil.Disk",
                "health_check.contrib.psutil.Memory",
                "health_check.contrib.celery.Ping",
            ],
        ),
    ),
    path(
        "graphql/",
        csrf_exempt(
            CustomAsyncGraphQLView.as_view(**base_graphql_kwargs),
        ),
        name="graphql",
    ),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "graphiql/",
            csrf_exempt(
                CustomAsyncGraphQLView.as_view(
                    **base_graphql_kwargs,
                    graphql_ide="graphiql",
                ),
            ),
            name="graphiql",
        ),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    _cog_test = settings.BASE_DIR / "dummy" / "cog-test.html"
    _cog_test_2 = settings.BASE_DIR / "dummy" / "cog_test_2.html"
    urlpatterns += [
        path("cog-test/", lambda r: FileResponse(_cog_test.open("rb"), content_type="text/html")),
        path("cog-test-2/", lambda r: FileResponse(_cog_test_2.open("rb"), content_type="text/html")),
    ]
