# finished/admin.py
from django.contrib import admin
from .models import FinishedRecipe, FinishedRecipeIngredient, FinishedProduction


class FinishedRecipeIngredientInline(admin.TabularInline):
    model = FinishedRecipeIngredient
    extra = 1
    fields = ['product', 'kilos']


@admin.register(FinishedRecipe)
class FinishedRecipeAdmin(admin.ModelAdmin):
    list_display = ['name', 'finished_product', 'ingredients_count', 'total_kg', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'finished_product__name']
    inlines = [FinishedRecipeIngredientInline]
    readonly_fields = ['created_at', 'total_kg']


@admin.register(FinishedProduction)
class FinishedProductionAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'branch', 'quantity', 'produced_by', 'produced_at']
    list_filter = ['branch', 'produced_at']
    search_fields = ['recipe__name', 'branch__name']
    readonly_fields = ['produced_at']