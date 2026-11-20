"""The sfstack caller must not silently authorize automated or mutable Factory work."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CALLER = ROOT / ".github/workflows/sfstack-quality.yml"
EXPECTED_FACTORY = "3921ac399844641976bacfc68385c3f3907491d2"


class PinnedFactoryCallerTests(unittest.TestCase):
    def test_manual_only_source_uses_exact_factory_sha(self):
        source = CALLER.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:\n", source)
        self.assertNotRegex(source, r"(?m)^\s+(?:pull_request_target|pull_request|push|schedule):")
        self.assertIn(
            "uses: grove/factory/.github/workflows/sfstack-quality.yml@" + EXPECTED_FACTORY,
            source,
        )
        self.assertRegex(EXPECTED_FACTORY, r"^[0-9a-f]{40}$")
        self.assertNotIn("@main", source)
        self.assertNotIn("@latest", source)
        self.assertIn(
            "run-name: \"sfstack quality / PR #$" + "{{ inputs.pr-number }} / request manual\"",
            source,
        )
        self.assertIn("github.event.repository.default_branch", source)

    def test_caller_does_not_fetch_or_run_untrusted_controller_code(self):
        source = CALLER.read_text(encoding="utf-8")
        # No token-altering shell step, local runtime checkout or arbitrary
        # caller-provided factory SHA. The callee retains separate write jobs.
        self.assertNotIn("actions/checkout@", source)
        self.assertNotIn("run: |", source)
        self.assertNotIn("pull-requests: write", source)
        self.assertNotIn("contents: write", source)
        self.assertIn("  checks: write", source)
        self.assertIn("  actions: read", source)
        self.assertIn(
            "COPILOT_GITHUB_TOKEN: $" + "{{ secrets.COPILOT_GITHUB_TOKEN }}", source
        )
        self.assertEqual(1, source.count("    uses: grove/factory/"))

if __name__ == "__main__":
    unittest.main()
