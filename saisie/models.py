from django.db import models

class Client(models.Model):
    nom = models.CharField(max_length=100, verbose_name="Nom du client")
    email = models.EmailField(verbose_name="Adresse email")
    telephone = models.CharField(max_length=20, verbose_name="Téléphone")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")
    
    def __str__(self):
        return self.nom
    
    class Meta:
        db_table = 'clients'
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['-date_creation']