import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        self.settings = self.project / ".claude/settings.json"
        self.install()

    def install(self):
        subprocess.run(["bash", ROOT / "install.sh", "--project", self.project],
                       check=True, stdout=subprocess.DEVNULL)

    def test_reinstall_preserves_sibling_command_and_matcher(self):
        config = json.loads(self.settings.read_text())
        group = config["hooks"]["SessionStart"][0]
        other = {"type": "command", "command": "echo keep"}
        group["hooks"].append(other)
        group["matcher"] = "resume"
        self.settings.write_text(json.dumps(config))
        self.install()
        self.install()
        preserved, guard = json.loads(self.settings.read_text())["hooks"]["SessionStart"]
        self.assertEqual(preserved, {"matcher": "resume", "hooks": [other]})
        self.assertTrue(guard["_ip_guard"])

    def test_expired_history_and_https_fallback(self):
        curl = self.project / "curl"
        curl.write_text("""#!/bin/bash
case "${*: -1}" in
  https://api.anthropic.com/*) echo 401 ;;
  https://ipwho.is/*) echo '{"success":true,"ip":"192.0.2.1","country_code":"US"}' ;;
  *) exit 1 ;;
esac
""")
        curl.chmod(0o755)
        cache = self.project / ".cache/claude-ip-guard"
        cache.mkdir(parents=True)
        history = cache / "ip_history.jsonl"
        history.write_text('{"time":"2000-01-01","ip":"192.0.2.2"}\n')
        env = dict(os.environ, HOME=str(self.project), ANTHROPIC_BASE_URL="",
                   PATH=f"{self.project}:{os.environ['PATH']}")
        subprocess.run(["bash", ".claude/scripts/check-ip-on-prompt.sh"],
                       cwd=self.project, env=env, check=True)
        self.assertEqual(json.loads(history.read_text())["ip"], "192.0.2.1")
        self.assertIn("|US|", (cache / "ip_cache").read_text())


if __name__ == "__main__":
    unittest.main()
