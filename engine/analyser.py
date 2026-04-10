import pyodbc
from datetime import datetime

class AnalyseurTables:
    def __init__(self, serveur, base_donnees):
        self.serveur = serveur
        self.base_donnees = base_donnees
        self.conn = None
        self.cursor = None
    
    def connecter(self):
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.serveur.ip_address},{self.serveur.port};"
            f"DATABASE={self.base_donnees};"
            f"UID={self.serveur.username};"
            f"PWD={self.serveur.password};"
            f"TrustServerCertificate=yes;"
        )
        self.conn = pyodbc.connect(conn_str, timeout=30)
        self.cursor = self.conn.cursor()
    
    def fermer(self):
        if self.conn:
            self.conn.close()
    
    def get_tables(self):
        self.cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        return [row[0] for row in self.cursor.fetchall()]
    
    def analyser_table(self, table_name):
        data = {
            'table_name': table_name,
            'a_pk': False,
            'a_index': False,
            'jamais_utilisee': True,
            'nb_fk': 0,
            'nb_check': 0,
            'nb_colonnes': 0,
            'nb_nullables': 0,
            'nb_doublons': 0,
            'nb_lignes': 0,
            'taille_mb': 0,
            'nb_procedures': 0,
            'nb_vues': 0,
            'derniere_modification': None,
            'derniere_procedure': None
        }
        
        # 1. Vérifier PK
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
            WHERE TABLE_NAME = '{table_name}' AND CONSTRAINT_TYPE = 'PRIMARY KEY'
        """)
        data['a_pk'] = self.cursor.fetchone()[0] > 0
        
        # 2. Vérifier index (clustered ou nonclustered)
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM sys.indexes 
            WHERE object_id = OBJECT_ID('{table_name}') AND index_id > 0
        """)
        data['a_index'] = self.cursor.fetchone()[0] > 0
        
        # 3. Colonnes
        self.cursor.execute(f"""
            SELECT COUNT(*), SUM(CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END)
            FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'
        """)
        row = self.cursor.fetchone()
        data['nb_colonnes'] = row[0] or 0
        data['nb_nullables'] = row[1] or 0
        
        # 4. FK
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc 
                ON rc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = '{table_name}'
        """)
        data['nb_fk'] = self.cursor.fetchone()[0] or 0
        
        # 5. CHECK
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc 
                ON cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = '{table_name}'
        """)
        data['nb_check'] = self.cursor.fetchone()[0] or 0
        
        # 6. Lignes
        try:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            data['nb_lignes'] = self.cursor.fetchone()[0] or 0
        except:
            data['nb_lignes'] = 0
        
        # 7. Taille
        self.cursor.execute(f"""
            SELECT SUM(a.total_pages) * 8 / 1024.0
            FROM sys.partitions p
            JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE p.object_id = OBJECT_ID('{table_name}')
        """)
        data['taille_mb'] = round(self.cursor.fetchone()[0] or 0, 2)
        
        # 8. Dernière utilisation
        self.cursor.execute(f"""
            SELECT MAX(last_user_update)
            FROM sys.dm_db_index_usage_stats
            WHERE database_id = DB_ID() AND object_id = OBJECT_ID('{table_name}')
        """)
        last_use = self.cursor.fetchone()[0]
        if last_use:
            data['derniere_modification'] = last_use
            data['jamais_utilisee'] = False
        
        # 9. Procédures et vues (comptage séparé)
        self.cursor.execute(f"""
            SELECT COUNT(*) FROM sys.sql_modules m
            JOIN sys.objects o ON m.object_id = o.object_id
            WHERE o.type = 'P'
            AND m.definition LIKE '%{table_name}%'
        """)
        data['nb_procedures'] = self.cursor.fetchone()[0] or 0

        self.cursor.execute(f"""
            SELECT COUNT(*) FROM sys.sql_modules m
            JOIN sys.objects o ON m.object_id = o.object_id
            WHERE o.type = 'V'
            AND m.definition LIKE '%{table_name}%'
        """)
        data['nb_vues'] = self.cursor.fetchone()[0] or 0

        # 10. Doublons (groupés sur toutes les colonnes)
        if data['nb_lignes'] > 0:
            self.cursor.execute(
                """
                SELECT QUOTENAME(COLUMN_NAME)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """,
                table_name,
            )
            columns = [row[0] for row in self.cursor.fetchall()]
            if columns:
                group_by = ", ".join(columns)
                table_quoted = f"[{table_name}]"
                duplicates_sql = (
                    f"SELECT SUM(cnt - 1) FROM ("
                    f"SELECT COUNT(*) AS cnt FROM {table_quoted} "
                    f"GROUP BY {group_by} HAVING COUNT(*) > 1"
                    f") d"
                )
                try:
                    self.cursor.execute(duplicates_sql)
                    data['nb_doublons'] = self.cursor.fetchone()[0] or 0
                except:
                    data['nb_doublons'] = 0
        
        return data
    
    def analyser_toutes_tables(self):
        tables_data = []
        tables = self.get_tables()
        
        for table in tables:
            try:
                data = self.analyser_table(table)
                tables_data.append(data)
            except Exception as e:
                print(f"Erreur sur {table}: {e}")
                continue
        
        return tables_data