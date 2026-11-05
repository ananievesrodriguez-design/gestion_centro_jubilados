import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "unit-test-key")
os.environ.setdefault("SECRET_KEY", "unit-test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost/test")

os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "unit-test-key"
os.environ["SECRET_KEY"] = "unit-test-secret"
os.environ["DATABASE_URL"] = "postgresql://localhost/test"

import whatsapp_service


class WhatsAppServiceTests(unittest.TestCase):
    def setUp(self):
        self.token = whatsapp_service.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = whatsapp_service.WHATSAPP_PHONE_NUMBER_ID
        whatsapp_service.WHATSAPP_ACCESS_TOKEN = "test-token"
        whatsapp_service.WHATSAPP_PHONE_NUMBER_ID = "123456789"

    def tearDown(self):
        whatsapp_service.WHATSAPP_ACCESS_TOKEN = self.token
        whatsapp_service.WHATSAPP_PHONE_NUMBER_ID = self.phone_number_id

    @patch("whatsapp_service.urlopen")
    def test_sends_template_with_normalized_argentinian_phone(self, urlopen_mock):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        urlopen_mock.return_value = response

        whatsapp_service.send_whatsapp_template(
            "+54 9 383 412 3456",
            "cumpleanos_aprobado",
            ["Ana"],
        )

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["to"], "5493834123456")
        self.assertEqual(payload["template"]["name"], "cumpleanos_aprobado")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"][0]["text"],
            "Ana",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    @patch("whatsapp_service.urlopen")
    def test_rejects_phone_without_country_code(self, urlopen_mock):
        with self.assertRaises(ValueError):
            whatsapp_service.send_whatsapp_template(
                "3834123456",
                "cumpleanos_aprobado",
                ["Ana"],
            )

        urlopen_mock.assert_not_called()

    def test_rejects_unconfigured_whatsapp(self):
        whatsapp_service.WHATSAPP_ACCESS_TOKEN = None

        with self.assertRaises(ValueError):
            whatsapp_service.send_whatsapp_template(
                "+54 9 383 412 3456",
                "cumpleanos_aprobado",
                ["Ana"],
            )


if __name__ == "__main__":
    unittest.main()
