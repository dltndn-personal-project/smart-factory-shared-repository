"""Small regression checks for the ledger's publication rules."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import auto_approval
import validate_shared as validator


class SharedValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original_root = validator.ROOT
        validator.ROOT = self.root
        (self.root / "issues").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "docs/INTERFACES.md").write_text("original\n")
        (self.root / ".github").mkdir()
        (self.root / ".github/CODEOWNERS").write_text("* @acme/contract-owners\n/issues/\n")
        self.first = self.message()
        self.write_issue(self.first)
        self.write_index([self.first])
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        validator.ROOT = self.original_root
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True)

    def message(self, related=None):
        return {
            "issue_id": f"ISSUE-{uuid4()}",
            "type": "MESSAGE",
            "source": {"component": "producer", "task": "TASK-1"},
            "created_at": "2026-01-01T00:00:00Z",
            "summary": "Check delivery",
            "attention": ["consumer"],
            "related_issues": related or [],
            "observation": "Observed missing data",
            "requested_action": None,
            "evidence": [],
            "follow_up": {"owner": None, "done_when": None},
        }

    def write_issue(self, issue):
        path = self.root / "issues" / f"{issue['issue_id']}.yaml"
        path.write_text(json.dumps(issue))  # JSON is valid YAML.

    def write_index(self, issues):
        entries = [
            {field: issue[field] for field in ("issue_id", "type", "summary", "attention")}
            | {"path": f"issues/{issue['issue_id']}.yaml"}
            for issue in issues
        ]
        (self.root / "issues/index.json").write_text(json.dumps({"issues": entries}))

    def test_new_issue_is_valid_but_published_issue_is_immutable(self):
        second = self.message([self.first["issue_id"]])
        self.write_issue(second)
        self.write_index([self.first, second])
        validator.validate(self.base)

        self.first["observation"] = "silently edited"
        self.write_issue(self.first)
        with self.assertRaisesRegex(ValueError, "immutable"):
            validator.validate(self.base)

    def test_reordering_or_unindexed_issue_is_rejected(self):
        second = self.message()
        self.write_issue(second)
        with self.assertRaisesRegex(ValueError, "missing from issues/index.json"):
            validator.validate(self.base)
        self.write_index([second, self.first])
        with self.assertRaisesRegex(ValueError, "unchanged prefix"):
            validator.validate(self.base)

    def test_document_edit_needs_matching_new_change_issue(self):
        (self.root / "docs/INTERFACES.md").write_text("revised\n")
        with self.assertRaisesRegex(ValueError, "DOCUMENT_CHANGE"):
            validator.validate(self.base)

        change = self.message()
        change.update({
            "type": "DOCUMENT_CHANGE",
            "reason": "Clarify delivery",
            "changed_documents": [{"file": "docs/INTERFACES.md", "section": "delivery"}],
            "change": {"before": "unspecified", "after": "specified"},
            "compatibility": "Clarification only",
            "transition": {"adoption": "review", "rollback": "revert"},
        })
        self.write_issue(change)
        self.write_index([self.first, change])
        validator.validate(self.base)

        change["compatibility"] = {"breaking": False, "rationale": "clarification"}
        self.write_issue(change)
        with self.assertRaisesRegex(ValueError, "compatibility"):
            validator.validate(self.base)

    def test_agent_core_edit_needs_a_change_issue(self):
        (self.root / "agent-core/process").mkdir(parents=True)
        (self.root / "agent-core/process/40-verify.md").write_text("clarified\n")
        with self.assertRaisesRegex(ValueError, "agent-core/process/40-verify.md"):
            validator.validate(self.base)

    def test_document_edits_before_first_issue_are_initialization(self):
        (self.root / "issues" / f"{self.first['issue_id']}.yaml").unlink()
        self.write_index([])
        self.git("commit", "-qam", "empty ledger")
        empty_base = self.git("rev-parse", "HEAD").strip()

        (self.root / "docs/INTERFACES.md").write_text("initial contract\n")
        validator.validate(empty_base)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "change")

    def test_only_new_messages_are_approved_automatically(self):
        second = self.message([self.first["issue_id"]])
        self.write_issue(second)
        self.write_index([self.first, second])
        self.commit()
        self.assertEqual(auto_approval.problems(self.base), [])

        (self.root / "AGENTS.md").write_text("changed rules\n")
        self.commit()
        self.assertEqual(auto_approval.problems(self.base), ["AGENTS.md: only new Issues and issues/index.json are approved automatically"])

    def test_document_change_or_placeholder_owner_needs_a_human(self):
        (self.root / "docs/INTERFACES.md").write_text("revised\n")
        change = self.message()
        change.update({
            "type": "DOCUMENT_CHANGE",
            "reason": "Clarify delivery",
            "changed_documents": [{"file": "docs/INTERFACES.md", "section": "delivery"}],
            "change": {"before": "unspecified", "after": "specified"},
            "compatibility": "Clarification only",
            "transition": {"adoption": "review", "rollback": "revert"},
        })
        self.write_issue(change)
        self.write_index([self.first, change])
        self.commit()
        self.assertTrue(any("DOCUMENT_CHANGE" in problem for problem in auto_approval.problems(self.base)))

        (self.root / ".github/CODEOWNERS").write_text("* @<owner>\n/issues/\n")
        self.commit()
        placeholder_base = self.git("rev-parse", "HEAD").strip()
        message = self.message()
        self.write_issue(message)
        self.write_index([self.first, change, message])
        self.commit()
        self.assertEqual(auto_approval.problems(placeholder_base), [".github/CODEOWNERS needs a real owner for *"])


if __name__ == "__main__":
    unittest.main()
