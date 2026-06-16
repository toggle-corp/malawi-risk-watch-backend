import typing

from django.conf import settings
from django.core.files.storage import storages
from django.db import models


class OverwritableFileField(models.FileField):
    def __new__init__(self, *args: typing.Any, **kwargs: typing.Any):
        kwargs.setdefault("storage", storages[settings.STORAGE_OVERWRITE_KEY])
        super().__init__(*args, **kwargs)

    @typing.override
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # This is also default_storage (with overwrite change)
        # FileField doesn't track default_storage in migrations
        # So we are also untracking the storage which is added by the FileField deconstruct
        if self.storage is storages[settings.STORAGE_OVERWRITE_KEY]:
            kwargs.pop("storage")
        return name, path, args, kwargs


# XXX: monkey patching to avoid removing OverwritableFileField.__init__ type annotations
OverwritableFileField.__init__ = OverwritableFileField.__new__init__
