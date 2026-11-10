"""Verifica la conexión a la base de datos y muestra qué base se está usando.

Uso:  python manage.py verificar_bd
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Revisa la conexión con la base de datos y resume su estado."

    def handle(self, *args, **options):
        cfg = connection.settings_dict
        self.stdout.write(self.style.MIGRATE_HEADING("Configuración de la base de datos"))
        self.stdout.write(f"  Motor : {cfg['ENGINE']}")
        self.stdout.write(f"  Nombre: {cfg['NAME']}")
        if cfg.get("HOST"):
            self.stdout.write(f"  Host  : {cfg['HOST']}:{cfg.get('PORT', '')}")

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            raise CommandError(f"No fue posible conectar con la base de datos: {exc}")
        self.stdout.write(self.style.SUCCESS("  Conexión: OK (SELECT 1 respondió)"))

        executor = MigrationExecutor(connection)
        pendientes = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pendientes:
            self.stdout.write(self.style.WARNING(
                f"  Migraciones pendientes: {len(pendientes)} (ejecuta: python manage.py migrate)"))
        else:
            self.stdout.write(self.style.SUCCESS("  Migraciones: todas aplicadas"))

        self.stdout.write(self.style.MIGRATE_HEADING("Registros por tabla (app tienda)"))
        for modelo in apps.get_app_config("tienda").get_models():
            self.stdout.write(f"  {modelo._meta.db_table:<28} {modelo.objects.count():>10,}")
