import typing
from datetime import datetime
from enum import Enum

from django.db import models
from django.test import TestCase as BaseTestCase
from django.test import override_settings

# Used by CI to trigger the migration check without running real tests.
FakeTest = None


@override_settings(
    DEBUG=True,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class TestCase(BaseTestCase):
    def force_login(self, user) -> None:  # type: ignore[reportMissingParameterType]
        self.client.force_login(user)

    def logout(self) -> None:
        self.client.logout()

    def query_check(
        self,
        query: str,
        assert_errors: bool = False,
        variables: dict[typing.Any, typing.Any] | None = None,
        **kwargs,  # type: ignore[reportMissingParameterType]
    ) -> dict[typing.Any, typing.Any]:

        response = self.client.post(
            "/graphql/",
            data={"query": query, "variables": variables},
            content_type="application/json",
            **kwargs,
        )

        if assert_errors:
            self.assertResponseHasErrors(response)
        else:
            self.assertResponseNoErrors(response)
        return response.json()

    def assertResponseNoErrors(self, resp: typing.Any, msg=None) -> None:  # type: ignore[reportMissingParameterType]
        content = resp.json()
        assert resp.status_code == 200, msg or content
        assert "errors" not in list(content.keys()), msg or content

    def assertResponseHasErrors(self, resp: typing.Any, msg=None) -> None:  # type: ignore[reportMissingParameterType]
        content = resp.json()
        assert "errors" in list(content.keys()), msg or content

    @staticmethod
    def genum(_enum: models.TextChoices | models.IntegerChoices | Enum) -> str | None:
        if _enum:
            return _enum.name
        return None

    def gdatetime(self, _datetime: datetime | None) -> str | None:
        if _datetime:
            return _datetime.isoformat()
        return None

    def gID(self, pk: typing.Any) -> str | None:
        if pk:
            return str(pk)
        return None

    def g_pagination(
        self,
        *,
        offset: int,
        limit: int,
        total_count: int,
        results: list[typing.Any],
    ) -> dict[str, typing.Any]:
        return {
            "totalCount": total_count,
            "pageInfo": {"offset": offset, "limit": limit},
            "results": results,
        }

    def g_mutation_response(
        self,
        *,
        errors: typing.Any = None,
        ok: bool,
        result: typing.Any,
    ) -> dict[str, typing.Any]:
        return {"errors": errors, "ok": ok, "result": result}
