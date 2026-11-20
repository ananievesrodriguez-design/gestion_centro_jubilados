import unittest
from io import BytesIO
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

import portal_storage


class PortalStorageTests(unittest.TestCase):
    def test_recognizes_only_storage_photo_paths(self):
        self.assertTrue(portal_storage.es_foto_en_storage("fotos/abc123.jpg"))
        self.assertFalse(portal_storage.es_foto_en_storage("portal_foto_123.jpg"))
        self.assertFalse(portal_storage.es_foto_en_storage("fotos/../private.jpg"))

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
        self.assertEqual(args[1].read(), b"image-bytes")
        self.assertEqual(args[2]["content-type"], "image/jpeg")

    @patch("portal_storage.SUPABASE_SERVICE_ROLE_KEY", "")
    def test_requires_service_key_to_upload(self):
        archivo = FileStorage(stream=BytesIO(b"image-bytes"), filename="foto.jpg")

        with self.assertRaisesRegex(RuntimeError, "SUPABASE_SERVICE_ROLE_KEY"):
            portal_storage.subir_foto_portal(archivo, archivo.filename)


if __name__ == "__main__":
    unittest.main()
