from django.contrib import admin

from .models import AnalyseBase, AnalyseTable, LLMResponseLog


@admin.register(AnalyseTable)
class AnalyseTableAdmin(admin.ModelAdmin):
	list_display = ("serveur", "base_donnees", "table_name", "date_analyse", "a_pk", "a_index", "nb_lignes")
	list_filter = ("serveur", "base_donnees", "a_pk", "a_index", "jamais_utilisee")
	search_fields = ("base_donnees", "table_name")


@admin.register(AnalyseBase)
class AnalyseBaseAdmin(admin.ModelAdmin):
	list_display = ("serveur", "base_donnees", "date_analyse", "score", "nb_tables")
	list_filter = ("serveur", "base_donnees")
	search_fields = ("base_donnees",)


@admin.register(LLMResponseLog)
class LLMResponseLogAdmin(admin.ModelAdmin):
	list_display = ("created_at", "model_name", "latency_ms")
	list_filter = ("model_name", "created_at")
	search_fields = ("question", "answer")

