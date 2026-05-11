from django.contrib import admin

from .models import AdminArea


@admin.register(AdminArea)
class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ["pcode", "name", "level", "parent", "country_iso"]
    list_filter = ["level", "country_iso"]
    search_fields = ["name", "pcode"]
    ordering = ["level", "name"]
