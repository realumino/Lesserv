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


def _fixture_config():
    """A minimal config with two inbounds and two outbounds for tests."""
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


class TestSaveConfig(unittest.TestCase):
    """Atomically write a config dict to the configured path."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = mock.patch(
            "backend.services.xray_service.settings.CONFIG_PATH",
            os.path.join(self.tmpdir, "config.json"),
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_save_config_writes_valid_json(self):
        content = {"inbounds": [], "outbounds": [], "routing": {}}
        xray_service.save_config(content)

        path = os.path.join(self.tmpdir, "config.json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            written = json.load(handle)
        self.assertEqual(written, content)

    def test_save_config_creates_directory(self):
        deeper = os.path.join(self.tmpdir, "nested", "config.json")
        self.patcher.stop()
        self.patcher = mock.patch(
            "backend.services.xray_service.settings.CONFIG_PATH", deeper
        )
        self.patcher.start()

        xray_service.save_config({"test": True})
        self.assertTrue(os.path.exists(deeper))


class TestLoadRuntimeConfig(unittest.TestCase):
    """Read the generated runtime config back, tolerating missing/corrupt files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "xray_runtime.json")
        self.patcher = mock.patch(
            "backend.services.xray_service.settings.RUNTIME_CONFIG_PATH", self.path
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_load_runtime_config_returns_dict_after_write(self):
        content = {"inbounds": [], "outbounds": [], "routing": {}}
        xray_service.write_runtime_config(content)
        self.assertEqual(xray_service.load_runtime_config(), content)

    def test_load_runtime_config_none_when_missing(self):
        self.assertIsNone(xray_service.load_runtime_config())

    def test_load_runtime_config_none_when_malformed(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertIsNone(xray_service.load_runtime_config())

    def test_runtime_mtime_none_when_missing(self):
        self.assertIsNone(xray_service.runtime_mtime())

    def test_runtime_mtime_returns_timestamp_after_write(self):
        xray_service.write_runtime_config({"a": 1})
        self.assertIsInstance(xray_service.runtime_mtime(), int)


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

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_inbounds_returns_summaries(self, mock_load):
        mock_load.return_value = _fixture_config()

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

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_inbounds_503_when_no_config(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_inbounds
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_inbounds()
        self.assertEqual(ctx.exception.status_code, 503)

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_outbounds_returns_summaries(self, mock_load):
        mock_load.return_value = _fixture_config()

        from backend.routers.system import get_outbounds
        result = get_outbounds()

        self.assertEqual(
            result,
            [
                {"tag": "JAPAN", "protocol": "wireguard"},
                {"tag": "BLOCK", "protocol": "blackhole"},
            ],
        )

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_outbounds_503_when_no_config(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_outbounds
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_outbounds()
        self.assertEqual(ctx.exception.status_code, 503)

    @mock.patch("backend.routers.system.db.list_users")
    @mock.patch("backend.routers.system.xray_service.status")
    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_status_returns_composite(self, mock_load, mock_status, mock_list):
        mock_load.return_value = _fixture_config()
        mock_status.return_value = {"running": True, "pid": 42}
        mock_list.return_value = [{"username": "alice"}, {"username": "bob"}]

        from backend.routers.system import get_status
        result = get_status(conn=mock.MagicMock())

        self.assertEqual(
            result,
            {"config_loaded": True, "xray_running": True,
             "xray_pid": 42, "user_count": 2},
        )

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_get_config_returns_config(self, mock_load):
        config = _fixture_config()
        mock_load.return_value = config

        from backend.routers.system import get_config
        self.assertEqual(get_config(), config)

    @mock.patch("backend.routers.system.xray_service.load_config")
    def test_get_config_404_when_no_config(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_config
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_config()
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.system.xray_service.runtime_mtime")
    @mock.patch("backend.routers.system.xray_service.load_runtime_config")
    def test_runtime_config_returns_envelope(self, mock_load, mock_mtime):
        mock_load.return_value = {"inbounds": [], "outbounds": []}
        mock_mtime.return_value = 1789000000

        from backend.routers.system import get_runtime_config
        result = get_runtime_config()

        self.assertEqual(
            result,
            {"config": {"inbounds": [], "outbounds": []}, "generated_at": 1789000000},
        )

    @mock.patch("backend.routers.system.xray_service.load_runtime_config")
    def test_runtime_config_404_when_missing(self, mock_load):
        mock_load.return_value = None

        from backend.routers.system import get_runtime_config
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            get_runtime_config()
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.routers.system.xray_service.sync")
    @mock.patch("backend.routers.system.xray_service.save_config")
    def test_post_config_writes_and_syncs(self, mock_save, mock_sync):
        body = {"inbounds": [], "outbounds": [], "routing": {}}

        from backend.routers.system import post_config
        result = post_config(payload=body, conn=mock.MagicMock())

        mock_save.assert_called_once_with(body)
        mock_sync.assert_called_once()
        self.assertEqual(result, {"message": "config updated"})


class TestSync(unittest.TestCase):
    """The full sync wiring: keys generated, injected, runtime written."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        patchers = [
            mock.patch("backend.services.xray_service.settings.CONFIG_PATH",
                       os.path.join(self.tmpdir, "config.json")),
            mock.patch("backend.services.xray_service.settings.RUNTIME_CONFIG_PATH",
                       os.path.join(self.tmpdir, "runtime.json")),
            mock.patch("backend.services.xray_service.restart"),  # no subprocess
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _reality_config(self):
        return {
            "inbounds": [
                {
                    "tag": "REALITY",
                    "protocol": "vless",
                    "settings": {"clients": []},
                    "streamSettings": {
                        "security": "reality",
                        "realitySettings": {"privateKey": "operator-key"},
                    },
                }
            ],
            "outbounds": [],
        }

    def test_sync_generates_key_and_overwrites_private_key_in_runtime(self):
        from backend import db

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = db.connect(db_path)
        db.init_schema(conn)
        self.addCleanup(conn.close)

        xray_service.save_config(self._reality_config())
        xray_service.sync(conn)

        runtime = xray_service.load_runtime_config()
        stored = db.list_reality_keys(conn)["REALITY"]["private_key"]
        self.assertEqual(
            runtime["inbounds"][0]["streamSettings"]["realitySettings"]["privateKey"],
            stored,
        )
        # the operator's own config file stays untouched (DB is source of truth)
        self.assertEqual(
            xray_service.load_config()["inbounds"][0]["streamSettings"]["realitySettings"]["privateKey"],
            "operator-key",
        )

    def test_sync_puts_block_first_and_writes_no_catch_all_rule(self):
        from backend import db

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = db.connect(db_path)
        db.init_schema(conn)
        self.addCleanup(conn.close)

        config = self._reality_config()
        config["outbounds"] = [{"tag": "EXIT", "protocol": "freedom"}]
        xray_service.save_config(config)
        xray_service.sync(conn)

        runtime = xray_service.load_runtime_config()
        self.assertEqual(runtime["outbounds"][0]["tag"], "BLOCK")
        for rule in runtime["routing"]["rules"]:
            matchers = [k for k in rule if k != "outboundTag"]
            self.assertTrue(matchers, "matcher-less rule: %r" % rule)

    def test_sync_skips_when_no_config(self):
        from backend import db

        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = db.connect(db_path)
        db.init_schema(conn)
        self.addCleanup(conn.close)

        xray_service.sync(conn)  # must not raise or write anything

        self.assertIsNone(xray_service.load_runtime_config())
        self.assertEqual(db.list_reality_keys(conn), {})


if __name__ == "__main__":
    unittest.main()
