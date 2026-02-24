
from django.db import models

class Server(models.Model):
    name = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=1433)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    databases = models.TextField(help_text="Bases de données reliées, séparées par une virgule")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    def get_databases_list(self):
        if self.databases:
            return [db.strip() for db in self.databases.split(',')]
        return []
    
    def __str__(self):
        return f"{self.name} ({self.ip_address})"
    
    def get_databases_list(self):
        """Retourne la liste des bases sous forme de liste Python"""
        if self.databases:
            return [db.strip() for db in self.databases.split(',')]
        return []
    
    def get_connection_string(self):
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.ip_address},{self.port};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"TrustServerCertificate=yes;"
        )