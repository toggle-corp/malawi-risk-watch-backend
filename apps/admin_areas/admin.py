from django.contrib import admin

from .models import AdminArea


@admin.register(AdminArea)
class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ["admin_code", "name", "level", "parent", "country_iso"]
    list_filter = ["level", "country_iso"]
    search_fields = ["name", "admin_code"]
    ordering = ["level", "name"]
