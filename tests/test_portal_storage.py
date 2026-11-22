import unittest
from io import BytesIO
from flask import Flask
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

import config
import portal_storage


class PortalStorageTests(unittest.TestCase):
    def test_institution_logo_uses_persisted_storage_path(self):
        app = Flask(__name__)
        with app.test_request_context():
            with patch("config.cargar_config", return_value={"institucion": {"logo": "logo-local.png"}}):
                with patch("models.db.session.execute") as execute:
                    with patch("portal_storage.url_publica_logo_institucional", return_value="https://storage/logo.png") as public_url:
                        execute.return_value.scalar_one_or_none.return_value = "logos/logo.png"

                        context = config.inject_global_context()

        self.assertEqual(context["INSTITUCION"]["logo_url"], "https://storage/logo.png")
        public_url.assert_called_once_with("logos/logo.png")

    def test_institution_logo_falls_back_to_existing_static_file(self):
        app = Flask(__name__)
        with app.test_request_context():
            with patch("config.cargar_config", return_value={"institucion": {"logo": "logo-local.png"}}):
                with patch("models.db.session.execute") as execute:
                    execute.return_value.scalar_one_or_none.return_value = None

                    context = config.inject_global_context()

        self.assertEqual(
            context["INSTITUCION"]["logo_url"],
            "/static/img/logo-local.png",
        )

    def test_recognizes_only_storage_photo_paths(self):
        self.assertTrue(portal_storage.es_foto_en_storage("fotos/abc123.jpg"))
        self.assertFalse(portal_storage.es_foto_en_storage("portal_foto_123.jpg"))
        self.assertFalse(portal_storage.es_foto_en_storage("fotos/../private.jpg"))

    def test_recognizes_only_storage_logo_paths(self):
        self.assertTrue(portal_storage.es_logo_en_storage("logos/abc123.png"))
        self.assertFalse(portal_storage.es_logo_en_storage("logo_institucional.png"))
        self.assertFalse(portal_storage.es_logo_en_storage("logos/../private.png"))

    @patch("portal_storage.supabase_admin")
    @patch("portal_storage.SUPABASE_SERVICE_ROLE_KEY", "server-key")
    def test_uploads_photo_to_persistent_bucket(self, supabase_admin):
        archivo = FileStorage(
            stream=BytesIO(b"image-bytes"),
            filename="foto.jpg",
            content_type="image/jpeg",
        )

        ruta = portal_storage.subir_foto_portal(archivo, archivo.filename)

        self.assertRegex(ruta, r"^fotos/[0-9a-f]{32}\.jpg$")
        supabase_admin.storage.from_.assert_called_once_with(portal_storage.SUPABASE_PORTAL_BUCKET)
        supabase_admin.storage.from_.return_value.upload.assert_called_once()
        args, kwargs = supabase_admin.storage.from_.return_value.upload.call_args
        self.assertEqual(args[0], ruta)
        self.assertEqual(args[1], b"image-bytes")
        self.assertEqual(args[2]["content-type"], "image/jpeg")

    @patch("portal_storage.supabase_admin")
    @patch("portal_storage.SUPABASE_SERVICE_ROLE_KEY", "server-key")
    def test_uploads_institutional_logo_under_logo_prefix(self, supabase_admin):
        archivo = FileStorage(
            stream=BytesIO(b"logo-bytes"),
            filename="logo.png",
            content_type="image/png",
        )

        ruta = portal_storage.subir_logo_institucional(archivo, archivo.filename)

        self.assertRegex(ruta, r"^logos/[0-9a-f]{32}\.png$")
        supabase_admin.storage.from_.return_value.upload.assert_called_once()

    @patch("portal_storage.SUPABASE_SERVICE_ROLE_KEY", "")
    def test_requires_service_key_to_upload(self):
        archivo = FileStorage(stream=BytesIO(b"image-bytes"), filename="foto.jpg")

        with self.assertRaisesRegex(RuntimeError, "SUPABASE_SERVICE_ROLE_KEY"):
            portal_storage.subir_foto_portal(archivo, archivo.filename)


if __name__ == "__main__":
    unittest.main()
