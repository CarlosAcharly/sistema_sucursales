from django.contrib import admin
from .models import Diet, DietBaseIngredient
from django.core.exceptions import ValidationError
from django.db.models import Sum


class DietBaseIngredientInline(admin.TabularInline):
    model = DietBaseIngredient
    extra = 1


@admin.register(Diet)
class DietAdmin(admin.ModelAdmin):
    inlines = [DietBaseIngredientInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        diet = form.instance
        total = diet.base_ingredients.aggregate(total=Sum('kilos'))['total'] or 0

        if total != 1000:
            raise ValidationError("La suma de los ingredientes debe ser exactamente 1000 kg.")
