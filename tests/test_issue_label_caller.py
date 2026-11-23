"""The label caller is narrow, SHA-pinned and not an issue-prose authority."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sfstack-issue-label.yml"
FACTORY = "234d7e4c12638daaa7497c1977d42b20215a433d"


class LabelCallerTests(unittest.TestCase):
    def test_only_human_issue_label_events_can_arrive(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  issues:\n    types: [labeled]", text)
        event = text.split("\non:\n", 1)[1].split("\nrun-name:", 1)[0]
        for forbidden in ("pull_request:", "pull_request_target:", "push:",
                          "workflow_run:", "issue_comment:", "schedule:"):
            self.assertNotIn(forbidden, event)
        self.assertIn("github.event.label.name == 'factory:plan'", text)
        self.assertIn("github.event.label.name == 'factory:run'", text)
        self.assertIn("!github.event.issue.pull_request", text)
        self.assertIn("github.repository == 'grove/sfstack'", text)
        self.assertIn("queue: max", text)
        self.assertIn("github.event.issue.number", text)

    def test_factory_source_and_callee_are_one_immutable_revision(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(FACTORY, r"^[a-f0-9]{40}$")
        self.assertIn("repository: grove/factory", text)
        self.assertIn("          ref: " + FACTORY, text)
        self.assertIn("uses: grove/factory/.github/workflows/sfstack-software.yml@" + FACTORY, text)
        self.assertEqual(3, text.count(FACTORY))
        self.assertNotIn("@main", text)
        self.assertNotIn("@latest", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("bootstrap_contracts.py", text)

    def test_paid_model_and_write_publisher_are_isolated(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        plan = text.split("\n  plan:\n", 1)[1].split("\n  publish_plan:\n", 1)[0]
        publish = text.split("\n  publish_plan:\n", 1)[1].split("\n  software:\n", 1)[0]
        self.assertIn("name: Generate actionable Copilot implementation proposal", plan)
        self.assertIn("node-version: '24'", plan)
        self.assertIn("npm install -g @github/copilot@1.0.114", plan)
        self.assertIn("--no-ask-user", plan)
        self.assertIn("--available-tools=view --deny-tool=write", plan)
        self.assertIn("COPILOT_GITHUB_TOKEN: $", plan)
        for disallowed in ("issues: write", "pull-requests: write", "actions: write",
                           "checks: write", "gh pr create", "github.api"):
            self.assertNotIn(disallowed, plan)
        self.assertIn("name: Revalidate exact issue and publish bounded", publish)
        self.assertIn("issues: write", publish)
        self.assertIn("--publish-ai", publish)
        self.assertNotIn("COPILOT_GITHUB_TOKEN", publish)
        self.assertNotIn("contents: write", publish)
        self.assertIn("sfstack-ai-plan-proposal-", plan)
        self.assertIn("sfstack-ai-plan-proposal-", publish)
        self.assertIn("needs.authorize.outputs.plan_requested == 'true'", plan)

    def test_plan_publisher_bootstraps_runtime_independently(self):
        # Regression for live issue #54: Copilot succeeded, but this fresh
        # publisher job imported software.py before jsonschema was installed.
        text = WORKFLOW.read_text(encoding="utf-8")
        auth = text.split("\n  authorize:\n", 1)[1].split("\n  plan:\n", 1)[0]
        publish = text.split("\n  publish_plan:\n", 1)[1].split("\n  software:\n", 1)[0]
        bootstrap = "python controller/tools/bootstrap_contracts.py"
        self.assertIn(bootstrap, auth)
        self.assertEqual(1, publish.count(bootstrap))
        self.assertLess(publish.index("actions/setup-python@"), publish.index(bootstrap))
        self.assertLess(publish.index(bootstrap), publish.index("--publish-ai"))
        self.assertIn("issues: write", publish)
        self.assertNotIn("COPILOT_GITHUB_TOKEN", publish)
        self.assertNotIn("contents: write", publish)

    def test_direct_run_and_optional_planner_remain_separate(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        auth = text.split("\n  authorize:\n", 1)[1].split("\n  plan:\n", 1)[0]
        model = text.split("\n  plan:\n", 1)[1].split("\n  publish_plan:\n", 1)[0]
        software = text.split("\n  software:\n", 1)[1]
        self.assertIn("github.event.label.name == 'factory:run'", auth)
        self.assertIn("if: github.event.label.name == 'factory:plan'", auth)
        self.assertIn("needs.authorize.outputs.plan_requested == 'true'", model)
        self.assertIn("needs.authorize.outputs.authorized == 'true'", software)
        self.assertNotIn("COPILOT_GITHUB_TOKEN", auth)
        self.assertNotIn("issues: write", model)
        self.assertIn("COPILOT_GITHUB_TOKEN", software)

    def test_publisher_rights_are_not_on_label_authorizer(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        auth = text.split("\n  authorize:\n", 1)[1].split("\n  plan:\n", 1)[0]
        downstream = text.split("\n  software:\n", 1)[1]
        self.assertIn("permissions: {}", text)
        self.assertIn("      issues: write", auth)
        self.assertIn("      contents: read", auth)
        self.assertIn("      actions: read", auth)
        for disallowed in ("contents: write", "checks: write", "pull-requests: write",
                           "actions: write", "COPILOT_GITHUB_TOKEN", "sfstack-build"):
            self.assertNotIn(disallowed, auth)
        self.assertIn("needs.authorize.outputs.authorized == 'true'", downstream)
        self.assertIn("fromJSON(needs.authorize.outputs.issue_number)", downstream)
        for field in ("allowed_paths", "acceptance_criteria", "repair_mode", "regression_file"):
            self.assertIn("needs.authorize.outputs." + field, downstream)
        self.assertIn("COPILOT_GITHUB_TOKEN: $", downstream)
        self.assertNotIn("pull_request_target:", text)
        self.assertNotIn("run: gh workflow run", text)
        self.assertNotIn("uses: ./.github/workflows", text)


if __name__ == "__main__":
    unittest.main()
