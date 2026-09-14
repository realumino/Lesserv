"""Tests for the system router and its new xray_service functions.

Run from the repo root:
    python -m unittest tests.test_system -v
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from backend.services import xray_service


def _fixture_template():
    """A minimal template with two inbounds and two outbounds for tests."""
    return {
        "log": {"loglevel": "debug"},
        "routing": {"rules": []},
        "inbounds": [
            {
                "tag": "REALITY",
                "protocol": "vless",
                "streamSettings": {"network": "tcp", "security": "reality"},
            },
            {"tag": "HTTP_ONLY", "protocol": "http"},
        ],
        "outbounds": [
            {"tag": "JAPAN", "protocol": "wireguard"},
            {"tag": "BLOCK", "protocol": "blackhole"},
        ],
    }


class TestSaveTemplate(unittest.TestCase):
    """Atomically write a template dict to the configured path."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = mock.patch(
            "backend.services.xray_service.settings.TEMPLATE_PATH",
            os.path.join(self.tmpdir, "template.json"),
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_save_template_writes_valid_json(self):
        content = {"inbounds": [], "outbounds": [], "routing": {}}
        xray_service.save_template(content)

        path = os.path.join(self.tmpdir, "template.json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            written = json.load(handle)
        self.assertEqual(written, content)

    def test_save_template_creates_directory(self):
        deeper = os.path.join(self.tmpdir, "nested", "template.json")
        self.patcher.stop()
        self.patcher = mock.patch(
            "backend.services.xray_service.settings.TEMPLATE_PATH", deeper
        )
        self.patcher.start()

        xray_service.save_template({"test": True})
        self.assertTrue(os.path.exists(deeper))


class TestLoadConfig(unittest.TestCase):
    """Read the generated config back, tolerating missing/corrupt files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "xray_config.json")
        self.patcher = mock.patch(
            "backend.services.xray_service.settings.XRAY_CONFIG_PATH", self.path
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_load_config_returns_dict_after_write(self):
        content = {"inbounds": [], "outbounds": [], "routing": {}}
        xray_service.write_config(content)
        self.assertEqual(xray_service.load_config(), content)

    def test_load_config_none_when_missing(self):
        self.assertIsNone(xray_service.load_config())

    def test_load_config_none_when_malformed(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(xray_service.load_config())

    def test_config_mtime_none_when_missing(self):
        self.assertIsNone(xray_service.config_mtime())

    def test_config_mtime_returns_timestamp_after_write(self):
        xray_service.write_config({"a": 1})
        self.assertIsInstance(xray_service.config_mtime(), int)


class TestStatus(unittest.TestCase):
    """Expose Xray subprocess health without side effects."""

    def tearDown(self):
        xray_service._process = None

    def test_status_when_no_process(self):
        xray_service._process = None
        result = xray_service.status()
        self.assertEqual(result, {"running": False, "pid": None})

    def test_status_when_process_is_running(self):
        proc = mock.MagicMock()
        proc.poll.return_value = None
        proc.pid = 42
        xray_service._process = proc

        result = xray_service.status()
        self.assertEqual(result, {"running": True, "pid": 42})

    def test_status_when_process_exited(self):
        proc = mock.MagicMock()
        proc.poll.return_value = 1
        xray_service._process = proc

        result = xray_service.status()
        self.assertEqual(result, {"running": False, "pid": None})


class TestSystemRouter(unittest.TestCase):
    """Call router endpoint functions directly with mocked dependencies."""

    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_inbounds_returns_summaries(self, mock_load):
        mock_load.return_value = _fixture_template()

        from backend.routers.system import get_inbounds
        result = get_inbounds()

        self.assertEqual(
            result,
            [
                {"tag": "REALITY", "protocol": "vless",
                 "network": "tcp", "security": "reality"},
                {"tag": "HTTP_ONLY", "protocol": "http",
                 "network": "", "security": ""},
            ],
        )

    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_inbounds_503_when_no_template(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_inbounds
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_inbounds()
        self.assertEqual(ctx.exception.status_code, 503)

    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_outbounds_returns_summaries(self, mock_load):
        mock_load.return_value = _fixture_template()

        from backend.routers.system import get_outbounds
        result = get_outbounds()

        self.assertEqual(
            result,
            [
                {"tag": "JAPAN", "protocol": "wireguard"},
                {"tag": "BLOCK", "protocol": "blackhole"},
            ],
        )

    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_outbounds_503_when_no_template(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_outbounds
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_outbounds()
        self.assertEqual(ctx.exception.status_code, 503)

    @mock.patch("backend.routers.system.db.list_users")
    @mock.patch("backend.routers.system.xray_service.status")
    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_status_returns_composite(self, mock_load, mock_status, mock_list):
        mock_load.return_value = _fixture_template()
        mock_status.return_value = {"running": True, "pid": 42}
        mock_list.return_value = [{"username": "alice"}, {"username": "bob"}]

        from backend.routers.system import get_status
        result = get_status(conn=mock.MagicMock())

        self.assertEqual(
            result,
            {"template_loaded": True, "xray_running": True,
             "xray_pid": 42, "user_count": 2},
        )

    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_get_config_returns_template(self, mock_load):
        template = _fixture_template()
        mock_load.return_value = template

        from backend.routers.system import get_config
        self.assertEqual(get_config(), template)

    @mock.patch("backend.routers.system.xray_service.load_template")
    def test_get_config_404_when_no_template(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_config
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_config()
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.system.xray_service.config_mtime")
    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_generated_config_returns_envelope(self, mock_load, mock_mtime):
        mock_load.return_value = {"inbounds": [], "outbounds": []}
        mock_mtime.return_value = 1789000000

        from backend.routers.system import get_generated_config
        result = get_generated_config()

        self.assertEqual(
            result,
            {"config": {"inbounds": [], "outbounds": []}, "generated_at": 1789000000},
        )

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_generated_config_404_when_missing(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_generated_config
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_generated_config()
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.system.xray_service.sync")
    @mock.patch("backend.routers.system.xray_service.save_template")
    def test_post_config_writes_and_syncs(self, mock_save, mock_sync):
        body = {"inbounds": [], "outbounds": [], "routing": {}}

        from backend.routers.system import post_config
        result = post_config(payload=body, conn=mock.MagicMock())

        mock_save.assert_called_once_with(body)
        mock_sync.assert_called_once()
        self.assertEqual(result, {"message": "config updated"})


if __name__ == "__main__":
    unittest.main()