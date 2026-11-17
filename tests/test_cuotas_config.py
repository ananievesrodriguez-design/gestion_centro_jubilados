import unittest
from decimal import Decimal

from cuotas_config import _valores_iniciales, parsear_valores_cuota


class CuotasConfigTests(unittest.TestCase):
    def test_reads_existing_values_and_legacy_names_for_initial_migration(self):
        valores = _valores_iniciales({
            "reglas_negocio": {
                "valor_cuota_estandar": 325,
                "valor_cuota_promocional": 1750,
                "valor_anual_estandar": 2400,
                "valor_inscripcion": 1900,
            }
        })

        self.assertEqual(valores["valor_cuota_mensual"], Decimal("325.00"))
        self.assertEqual(valores["valor_anual_promocional"], Decimal("1750.00"))
        self.assertEqual(valores["valor_anual_estandar"], Decimal("2400.00"))
        self.assertEqual(valores["valor_inscripcion"], Decimal("1900.00"))

    def test_parses_all_amounts_as_cents(self):
        valores = parsear_valores_cuota({
            "valor_cuota_mensual": "275.125",
            "valor_anual_promocional": "0",
            "valor_anual_estandar": "2100",
            "valor_inscripcion": "1800.50",
        })

        self.assertEqual(valores["valor_cuota_mensual"], Decimal("275.13"))
        self.assertEqual(valores["valor_anual_promocional"], Decimal("0.00"))
        self.assertEqual(valores["valor_anual_estandar"], Decimal("2100.00"))
        self.assertEqual(valores["valor_inscripcion"], Decimal("1800.50"))

    def test_rejects_missing_invalid_and_negative_amounts(self):
        base = {
            "valor_cuota_mensual": "200",
            "valor_anual_promocional": "1500",
            "valor_anual_estandar": "2000",
            "valor_inscripcion": "2000",
        }
        for campo, valor in (
            ("valor_inscripcion", ""),
            ("valor_cuota_mensual", "no es un monto"),
            ("valor_anual_estandar", "-1"),
            ("valor_anual_promocional", "NaN"),
            ("valor_inscripcion", "10000000000"),
        ):
            with self.subTest(campo=campo, valor=valor):
                formulario = {**base, campo: valor}
                with self.assertRaises(ValueError):
                    parsear_valores_cuota(formulario)


if __name__ == "__main__":
    unittest.main()
