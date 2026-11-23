"""The sfstack caller must not silently authorize automated or mutable Factory work."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CALLER = ROOT / ".github/workflows/sfstack-quality.yml"
EXPECTED_FACTORY = "2724639ff042459a9591181f8c2b1ef1b413f10b"


class PinnedFactoryCallerTests(unittest.TestCase):
    def test_quality_entrypoint_uses_exact_factory_sha(self):
        source = CALLER.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:\n", source)
        self.assertNotRegex(source, r"(?m)^\s+(?:pull_request_target|pull_request|push|schedule):")
        self.assertIn(
            "uses: grove/factory/.github/workflows/sfstack-quality.yml@" + EXPECTED_FACTORY,
            source,
        )
        self.assertRegex(EXPECTED_FACTORY, r"^[0-9a-f]{40}$")
        selected_uses = [line.strip() for line in source.splitlines()
                         if line.strip().startswith("uses: grove/factory/")]
        self.assertEqual(1, len(selected_uses))
        self.assertNotIn("@main", selected_uses[0])
        self.assertNotIn("@latest", selected_uses[0])
        self.assertIn(
            "run-name: \"sfstack quality / PR #$" + "{{ inputs.pr-number }} / request $" + "{{ inputs.request-id || 'manual' }}\"",
            source,
        )
        self.assertIn("github.event.repository.default_branch", source)
        # A step-level trust check must produce visible job evidence. The
        # reusable-workflow job has no condition that could fail before jobs
        # are materialized, and the preflight job has zero token permissions.
        self.assertIn("  preflight:\n", source)
        self.assertIn("permissions: {}", source)
        self.assertIn('run: test "$GITHUB_REF" = "$EXPECTED_REF"', source)
        self.assertIn("    needs: preflight", source)
        # GitHub may stringify workflow_dispatch numeric inputs before a
        # workflow_call; passing them directly can fail before any job exists.
        self.assertIn("      pr-number: $" + "{{ fromJSON(inputs.pr-number) }}", source)
        self.assertNotIn("      pr-number: $" + "{{ inputs.pr-number }}", source)
        self.assertNotIn("if: github.ref ==", source)

    def test_automatic_dispatch_handoff_preserves_exact_run_identity(self):
        source = CALLER.read_text(encoding="utf-8")
        self.assertIn('name: sfstack GitHub quality\n', source)
        self.assertIn('  workflow_dispatch:\n', source)
        for key in ('expected-head', 'expected-base', 'request-id'):
            self.assertIn('      ' + key + ':\n', source)
            self.assertIn('      ' + key + ': $' + '{{ inputs.' + key + ' }}', source)
        self.assertIn("inputs.request-id || 'manual'", source)
        self.assertIn("      pr-number: $" + "{{ fromJSON(inputs.pr-number) }}", source)
        # The Quality caller alone holds the Copilot secret and never directly
        # executes an untrusted PR event.
        self.assertNotIn("  pull_request:", source)
        self.assertNotIn("  workflow_run:", source)

    def test_token_free_same_repository_signal_and_pinned_coordinator(self):
        signal = (ROOT / ".github/workflows/sfstack-pr-signal.yml").read_text()
        event = (ROOT / ".github/workflows/sfstack-quality-events.yml").read_text()
        self.assertIn('name: sfstack PR signal\n', signal)
        self.assertIn('  pull_request:\n', signal)
        self.assertIn('types: [opened, reopened, synchronize, edited]', signal)
        self.assertNotIn('ready_for_review', signal)
        # Readiness is not a change in pinned head, base, or acceptance intent.
        self.assertIn('permissions: {}', signal)
        self.assertIn('github.event.pull_request.head.repo.full_name == github.repository', signal)
        self.assertIn('github.event.pull_request.base.ref == github.event.repository.default_branch', signal)
        for forbidden in ('pull_request_target:', 'actions/checkout@', 'secrets.',
                          'github.token', 'workflow_dispatch:', 'uses:'):
            self.assertNotIn(forbidden, signal)
        self.assertIn('name: sfstack quality events\n', event)
        self.assertIn('workflows: [sfstack PR signal, sfstack GitHub quality]', event)
        self.assertIn('types: [in_progress, completed]', event)
        self.assertIn('  push:\n    branches: [main]', event)
        self.assertIn('  actions: write', event)
        self.assertIn('  checks: write', event)
        self.assertIn(
            'uses: grove/factory/.github/workflows/sfstack-quality-events.yml@'
            + EXPECTED_FACTORY, event,
        )
        self.assertEqual(1, event.count('    uses: grove/factory/'))
        for forbidden in ('pull_request_target:', '  pull_request:', 'checkout@',
                          'secrets.', 'COPILOT_GITHUB_TOKEN', 'candidate'):
            # The event coordinator is metadata-only and does not fetch artifacts
            # or run a model. Ignore prose comments for "candidate".
            for line in event.splitlines():
                if not line.strip().startswith('#'):
                    self.assertNotIn(forbidden, line)
        self.assertNotIn('@main', event.split('uses: grove/factory/',1)[1].splitlines()[0])

    def test_manual_and_automatic_callers_pin_the_same_factory_source(self):
        signal = (ROOT / ".github/workflows/sfstack-pr-signal.yml").read_text()
        event = (ROOT / ".github/workflows/sfstack-quality-events.yml").read_text()
        quality = CALLER.read_text()
        self.assertEqual(1, quality.count('@' + EXPECTED_FACTORY))
        self.assertEqual(1, event.count('@' + EXPECTED_FACTORY))
        self.assertRegex(EXPECTED_FACTORY, r'^[a-f0-9]{40}$')
        self.assertIn('name: sfstack GitHub quality\n', quality)
        self.assertNotIn('COPILOT_GITHUB_TOKEN', signal + event)
        self.assertNotIn('pull_request_target', quality + signal + event)

    def test_required_quality_pr_check_is_eligible_and_read_only(self):
        source = (ROOT / ".github/workflows/sfstack-quality-required.yml").read_text()
        self.assertIn("name: sfstack quality required\n", source)
        self.assertIn("  pull_request:\n", source)
        self.assertIn("types: [opened, reopened, synchronize, edited]", source)
        self.assertIn("name: sfstack quality\n", source)
        self.assertIn("checks: read", source)
        self.assertIn("actions: read", source)
        self.assertIn("pull-requests: read", source)
        self.assertIn("permissions: {}", source)
        self.assertIn("repository: grove/factory", source)
        self.assertIn("ref: d2bb9be1fe9f472b5aaae99a33ad00810df6adfb", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn("working-directory: trusted", source)
        self.assertIn("required_quality_gate", source)
        for forbidden in ("pull_request_target:", "actions: write", "checks: write",
                          "contents: write", "COPILOT_GITHUB_TOKEN", "workflow_dispatch:"):
            self.assertNotIn(forbidden, source)

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
