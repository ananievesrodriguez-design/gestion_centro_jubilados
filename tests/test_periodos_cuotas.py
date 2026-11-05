import os
import unittest
from datetime import date

os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "unit-test-key"
os.environ["SECRET_KEY"] = "unit-test-secret"
os.environ["DATABASE_URL"] = "postgresql://localhost/test"

from routes.socios import _periodos_cubiertos


class PeriodosCuotasTests(unittest.TestCase):
    def test_uses_explicit_month_and_year(self):
        self.assertEqual(_periodos_cubiertos({"anio": 2026, "mes": 3}), {(2026, 3)})

    def test_reads_month_and_year_from_period_text(self):
        self.assertEqual(_periodos_cubiertos({"periodo": "Enero 2026"}), {(2026, 1)})

    def test_expands_annual_and_semester_periods(self):
        anual = _periodos_cubiertos({"periodo": "Cuota anual 2026"})
        primer_semestre = _periodos_cubiertos({"periodo": "Primer semestre 2026"})
        segundo_semestre = _periodos_cubiertos({"periodo": "2do semestre 2026"})

        self.assertEqual(anual, {(2026, mes) for mes in range(1, 13)})
        self.assertEqual(primer_semestre, {(2026, mes) for mes in range(1, 7)})
        self.assertEqual(segundo_semestre, {(2026, mes) for mes in range(7, 13)})

    def test_falls_back_to_collection_year_and_ignores_unknown_period(self):
        self.assertEqual(
            _periodos_cubiertos(
                {"periodo": "Período anterior", "fecha_cobro": date(2025, 6, 4)}
            ),
            set(),
        )
        self.assertEqual(
            _periodos_cubiertos(
                {"periodo": "Marzo", "fecha_cobro": date(2025, 6, 4)}
            ),
            {(2025, 3)},
        )


if __name__ == "__main__":
    unittest.main()
