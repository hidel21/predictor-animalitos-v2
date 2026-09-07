"""Integración: TEST_POSTGRES_URL debe apuntar a PostgreSQL de pruebas.

Crea y elimina únicamente un esquema aislado con nombre aleatorio.
"""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

from src.repositories import guardar_prediccion


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "Requiere PostgreSQL de pruebas")
class TestPredictionStorage(unittest.TestCase):
    def test_repeated_writes_and_database_guard(self):
        schema = "test_predictions_" + uuid.uuid4().hex
        admin = create_engine(os.environ["TEST_POSTGRES_URL"])
        engine = None
        root = Path(__file__).resolve().parents[1]
        try:
            with admin.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            engine = create_engine(
                os.environ["TEST_POSTGRES_URL"],
                connect_args={"options": f"-csearch_path={schema},public"},
            )
            with engine.begin() as conn:
                conn.execute(text((root / "schema.sql").read_text()))

            def save(_):
                return guardar_prediccion(
                    engine, date(2026, 9, 7), "10:00", "test",
                    5, [5, 6, 7], probs={"5": 0.3},
                )

            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertTrue(all(pool.map(save, range(24))))
            with engine.begin() as conn:
                original = conn.execute(text("SELECT * FROM predicciones")).one()
                conn.execute(text("UPDATE sorteos SET numero_real=5"))
                conn.execute(text("UPDATE predicciones SET acierto_top1=true"))
            save(0)
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT count(*) FROM predicciones")).scalar(), 1)
                self.assertEqual(conn.execute(text("SELECT creado_en FROM predicciones")).scalar(), original.creado_en)
                self.assertEqual(conn.execute(text("SELECT numero_real FROM sorteos")).scalar(), 5)

            guardar_prediccion(engine, date(2026, 9, 7), "10:00", "test", 5,
                               [5, 6, 7], probs={"5": 0.4})
            guardar_prediccion(engine, date(2026, 9, 7), "10:00", "test", 5,
                               [5, 6, 7], probs={"5": 0.3}, loteria="Lotto Activo")
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT count(*) FROM predicciones")).scalar(), 3)

            migration = (root / "scripts/prevenir_predicciones_repetidas.sql").read_text()
            migration = migration.replace("public.", f"{schema}.").replace(
                "pg_catalog, public", f"pg_catalog, {schema}")
            with engine.begin() as conn:
                conn.execute(text(migration))

            def legacy_insert(_):
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO predicciones(sorteo_id,modelo,top1,top3)
                        VALUES (:sid,'legacy',8,ARRAY[8,9,10])
                    """), {"sid": original.sorteo_id})

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(legacy_insert, range(24)))
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text(
                    "SELECT count(*) FROM predicciones WHERE modelo='legacy'"
                )).scalar(), 1)
        finally:
            if engine is not None:
                engine.dispose()
            with admin.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            admin.dispose()
