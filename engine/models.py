from django.db import models
from servers.models import Server

class AnalyseResultat(models.Model):
    serveur = models.ForeignKey(Server, on_delete=models.CASCADE)
    base_donnees = models.CharField(max_length=100)
    date_analyse = models.DateTimeField(auto_now_add=True)
    
    nombre_tables = models.IntegerField()
    total_lignes = models.IntegerField()
    total_null = models.IntegerField()
    total_doublons = models.IntegerField()
    total_anomalies = models.IntegerField()
    score_qualite = models.FloatField()
    
    class Meta:
        ordering = ['-date_analyse']