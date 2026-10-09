import subprocess
import unittest
from pathlib import Path


class SafeSyncScriptTests(unittest.TestCase):
    def test_script_has_valid_bash_syntax(self):
        script = Path(__file__).resolve().parents[1] / "tools" / "safe_sync_main.sh"
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
