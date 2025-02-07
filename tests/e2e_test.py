import os
import subprocess
import sys  # Import sys to access sys.executable
import unittest

class TestDockerhubCleanupE2E(unittest.TestCase):
    def test_cleanup_dry_run(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "dockerhub_cleanup.py")
        input_json_path = os.path.join(os.path.dirname(__file__), "dockerhub_backup_mock.json")
        cmd = [
            sys.executable,  # Use the same Python interpreter as the test
            script_path,
            "--namespace", "testnamespace",
            "--token", "dummy",
            "--dry-run",
            "--input-json", input_json_path,
            "--preserve", "pr-001:1", "pr-002:1"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, msg=f"Exit code: {result.returncode}; stderr: {result.stderr}")
        print(result.stdout)
        self.assertIn("Dry Run", result.stdout)
        self.assertIn("Would delete", result.stdout)
        self.assertNotIn("pr-001", result.stdout)
        self.assertNotIn("pr-002", result.stdout)

if __name__ == "__main__":
    unittest.main()
