"""The caller may choose a bounded issue, never a controller or permission grant."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOFTWARE = ROOT / ".github/workflows/sfstack-software.yml"
EXPECTED_FACTORY = "9c6388425058acf1eb46e1fb40408205c8f38268"


class PinnedSoftwareCallerTests(unittest.TestCase):
    def test_manual_only_same_repo_scope_and_immutable_factory_ref(self):
        source = SOFTWARE.read_text(encoding="utf-8")
        self.assertIn("name: sfstack GitHub software\n", source)
        self.assertIn('run-name: "sfstack software / issue #$', source)
        self.assertIn("  workflow_dispatch:\n", source)
        # Inspect only event keys. "issues: read" is the publisher's
        # *read permission*, not an issue event trigger.
        events = source.split("\non:\n", 1)[1].split("\nrun-name:", 1)[0]
        self.assertNotRegex(events, r"(?m)^\s+(?:pull_request|pull_request_target|push|schedule|issues):")
        self.assertRegex(EXPECTED_FACTORY, r"^[0-9a-f]{40}$")
        self.assertIn("uses: grove/factory/.github/workflows/sfstack-software.yml@" + EXPECTED_FACTORY, source)
        self.assertEqual(1, source.count("    uses: grove/factory/"))
        self.assertNotIn("@main", next(s for s in source.splitlines() if s.strip().startswith("uses: grove/factory")))
        self.assertNotIn("@latest", next(s for s in source.splitlines() if s.strip().startswith("uses: grove/factory")))

    def test_caller_forwards_explicit_typed_bounded_inputs_and_secret_only_to_factory(self):
        source = SOFTWARE.read_text(encoding="utf-8")
        for key in ("issue-number", "allowed-paths", "acceptance-criteria", "repair-mode", "regression-file"):
            self.assertIn("      " + key + ":\n", source)
        self.assertIn("      issue-number: $" + "{{ fromJSON(inputs.issue-number) }}", source)
        for key in ("allowed-paths", "acceptance-criteria", "repair-mode", "regression-file"):
            self.assertIn("      " + key + ": $" + "{{ inputs." + key + " }}", source)
        self.assertIn("COPILOT_GITHUB_TOKEN: $" + "{{ secrets.COPILOT_GITHUB_TOKEN }}", source)
        self.assertIn("    needs: preflight", source)
        self.assertIn("    permissions: {}", source)
        self.assertIn('run: test "$GITHUB_REF" = "$EXPECTED_REF"', source)
        self.assertNotIn("actions/checkout@", source)
        self.assertNotIn("gh api", source)
        self.assertNotIn("uses: ./.github/workflows", source)

    def test_publication_scope_requires_factory_to_narrow_mutation_jobs(self):
        source = SOFTWARE.read_text(encoding="utf-8")
        for key in ("contents: write", "pull-requests: write", "actions: write", "checks: write", "issues: read"):
            self.assertIn("  " + key, source)
        # No PR or issue event path may reach those permissions.
        for blocked in ("pull_request_target", "\n  pull_request:\n",
                        "\n  issues:\n", "\n  push:\n"):
            self.assertNotIn(blocked, source)
        quality = (ROOT / ".github/workflows/sfstack-quality.yml").read_text(encoding="utf-8")
        self.assertIn("name: sfstack GitHub quality\n", quality)
        self.assertIn("uses: grove/factory/.github/workflows/sfstack-quality.yml@", quality)
        self.assertNotIn("GITHUB_TOKEN", source.split("  software:\n", 1)[0].split("  preflight:\n", 1)[-1])


if __name__ == "__main__":
    unittest.main()
