import unittest

from comision_directiva import ordenar_integrantes_comision


class ComisionDirectivaTests(unittest.TestCase):
    def test_orders_positions_as_requested_and_groups_account_reviewers_by_type(self):
        integrantes = [
            {"cargo": "Revisor de cuentas suplente", "apellido": "Sosa", "nombre": "Ana"},
            {"cargo": "Vocal suplente 2", "apellido": "Vega", "nombre": "Luz"},
            {"cargo": "Vocal titular 2", "apellido": "Paz", "nombre": "Eva"},
            {"cargo": "Tesorera", "apellido": "Díaz", "nombre": "Mia"},
            {"cargo": "Revisor de cuentas titular", "apellido": "Luna", "nombre": "Sol"},
            {"cargo": "Presidente", "apellido": "Zárate", "nombre": "Noa"},
            {"cargo": "Vocal suplente 1", "apellido": "Iris", "nombre": "Lua"},
            {"cargo": "Secretaria", "apellido": "Alba", "nombre": "Ana"},
            {"cargo": "Vocal titular 1", "apellido": "Neri", "nombre": "Uma"},
        ]

        cargos = [integrante["cargo"] for integrante in ordenar_integrantes_comision(integrantes)]

        self.assertEqual(cargos, [
            "Presidente",
            "Secretaria",
            "Tesorera",
            "Vocal titular 1",
            "Vocal titular 2",
            "Vocal suplente 1",
            "Vocal suplente 2",
            "Revisor de cuentas titular",
            "Revisor de cuentas suplente",
        ])


if __name__ == "__main__":
    unittest.main()
