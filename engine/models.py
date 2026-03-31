from django.db import models
from servers.models import Server

class AnalyseTable(models.Model):
    # Contexte
    serveur = models.ForeignKey(Server, on_delete=models.CASCADE)
    base_donnees = models.CharField(max_length=100)
    table_name = models.CharField(max_length=200)
    date_analyse = models.DateTimeField(auto_now_add=True)
    
    # Métriques de structure
    a_pk = models.BooleanField(default=False)
    a_index = models.BooleanField(default=False)
    jamais_utilisee = models.BooleanField(default=False)
    
    # Métriques quantitatives
    nb_fk = models.IntegerField(default=0)
    nb_check = models.IntegerField(default=0)
    nb_colonnes = models.IntegerField(default=0)
    nb_nullables = models.IntegerField(default=0)
    nb_doublons = models.IntegerField(default=0)
    
    # Métriques temporelles
    derniere_modification = models.DateTimeField(null=True, blank=True)
    derniere_procedure = models.DateTimeField(null=True, blank=True)
    
    # Taille
    taille_mb = models.FloatField(default=0)
    nb_lignes = models.IntegerField(default=0)
    
    # Procédures et vues
    nb_procedures = models.IntegerField(default=0)
    nb_vues = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-date_analyse', 'base_donnees', 'table_name']
    
    def __str__(self):
        return f"{self.base_donnees}.{self.table_name}"

class AnalyseBase(models.Model):
    """Résumé par base de données"""
    serveur = models.ForeignKey(Server, on_delete=models.CASCADE)
    base_donnees = models.CharField(max_length=100)
    date_analyse = models.DateTimeField(auto_now_add=True)
    
    nb_tables = models.IntegerField(default=0)
    
    # Métriques agrégées
    tables_sans_pk = models.IntegerField(default=0)
    tables_sans_index = models.IntegerField(default=0)
    tables_jamais_utilisees = models.IntegerField(default=0)
    nb_procedures = models.IntegerField(default=0)
    nb_vues = models.IntegerField(default=0)
    nb_fk_total = models.IntegerField(default=0)
    score = models.FloatField(default=0)
    
    class Meta:
        ordering = ['-date_analyse']
    
    def __str__(self):
        return f"{self.base_donnees}"