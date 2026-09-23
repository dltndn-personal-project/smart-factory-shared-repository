#!/usr/bin/env python3
"""Validate the append-only Shared Issue ledger and its document changes."""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = re.compile(r"ISSUE-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")
INDEX_FIELDS = {"issue_id", "type", "summary", "attention", "path"}
# Contract documents and the shared agent process both change only through DOCUMENT_CHANGE.
GOVERNED = ("docs/", "agent-core/")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def mapping_with_unique_keys(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        require(key not in result, f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping_with_unique_keys)


def read_json(data, name):
    value = json.loads(data, object_pairs_hook=unique_pairs)
    require(isinstance(value, dict) and set(value) == {"issues"}, f"{name}: expected only an issues array")
    require(isinstance(value["issues"], list), f"{name}: issues must be an array")
    return value["issues"]


def read_yaml(data, name):
    value = yaml.load(data, Loader=UniqueKeyLoader)
    require(isinstance(value, dict), f"{name}: expected a mapping")
    return value


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label}: expected nonempty text")


def string_list(value, label):
    require(isinstance(value, list), f"{label}: expected an array")
    for item in value:
        nonempty(item, label)
    require(len(value) == len(set(value)), f"{label}: duplicate item")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)


def from_base(base, path):
    result = git("show", f"{base}:{path}")
    return result.stdout if result.returncode == 0 else None


def validate_issue(issue, name, earlier_ids=None):
    require("supersedes" not in issue, f"{name}: supersedes is not supported; publish a later Issue")
    kind = issue.get("type")
    require(kind in ("MESSAGE", "DOCUMENT_CHANGE"), f"{name}: invalid type")
    source = issue.get("source")
    require(isinstance(source, dict), f"{name}: source must be a mapping")
    for field in ("component", "task"):
        nonempty(source.get(field), f"{name}: source.{field}")
    nonempty(issue.get("summary"), f"{name}: summary")
    date = issue.get("created_at")
    require(isinstance(date, str) and UTC_TIMESTAMP.fullmatch(date), f"{name}: created_at must be a quoted UTC ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name}: invalid created_at") from exc
    require(parsed.utcoffset() == timezone.utc.utcoffset(parsed), f"{name}: created_at must be UTC")
    string_list(issue.get("attention"), f"{name}: attention")
    string_list(issue.get("related_issues"), f"{name}: related_issues")
    if earlier_ids is not None:
        for reference in issue["related_issues"]:
            require(reference in earlier_ids, f"{name}: related Issue must occur earlier in the index: {reference}")

    if kind == "MESSAGE":
        nonempty(issue.get("observation"), f"{name}: observation")
        action = issue.get("requested_action")
        require(action is None or isinstance(action, str) and bool(action.strip()), f"{name}: invalid requested_action")
        string_list(issue.get("evidence"), f"{name}: evidence")
        follow_up = issue.get("follow_up")
        require(isinstance(follow_up, dict), f"{name}: follow_up must be a mapping")
        for field in ("owner", "done_when"):
            value = follow_up.get(field)
            require(value is None or isinstance(value, str) and bool(value.strip()), f"{name}: invalid follow_up.{field}")
            if action:
                nonempty(value, f"{name}: follow_up.{field}")
    else:
        nonempty(issue.get("reason"), f"{name}: reason")
        documents = issue.get("changed_documents")
        require(isinstance(documents, list) and bool(documents), f"{name}: changed_documents must be nonempty")
        paths = []
        for document in documents:
            require(isinstance(document, dict), f"{name}: changed_documents entry must be a mapping")
            path = document.get("file")
            require(isinstance(path, str) and path.startswith(GOVERNED) and not Path(path).is_absolute() and ".." not in Path(path).parts, f"{name}: invalid document path")
            nonempty(document.get("section"), f"{name}: changed document section")
            paths.append(path)
        require(len(paths) == len(set(paths)), f"{name}: duplicate changed document")
        change = issue.get("change")
        require(isinstance(change, dict), f"{name}: change must be a mapping")
        for field in ("before", "after"):
            nonempty(change.get(field), f"{name}: change.{field}")
        nonempty(issue.get("compatibility"), f"{name}: compatibility")
        transition = issue.get("transition")
        require(isinstance(transition, dict), f"{name}: transition must be a mapping")
        for field in ("adoption", "rollback"):
            nonempty(transition.get(field), f"{name}: transition.{field}")


def validate(base=None):
    index = read_json((ROOT / "issues/index.json").read_text(), "issues/index.json")
    earlier = set()
    normalized_ids = set()
    new_changes = []
    old_index = None
    if base:
        require(re.fullmatch(r"[0-9a-fA-F]{40}", base), "--base must be a full commit SHA")
        require(git("merge-base", "--is-ancestor", base, "HEAD").returncode == 0, "--base must be an ancestor of HEAD")
        old_data = from_base(base, "issues/index.json")
        if old_data is not None:
            old_index = read_json(old_data, f"{base}:issues/index.json")
            require(index[: len(old_index)] == old_index, "issues/index.json: existing entries must remain an unchanged prefix")

    indexed_paths = set()
    for position, entry in enumerate(index):
        name = f"issues/index.json[{position}]"
        require(isinstance(entry, dict) and set(entry) == INDEX_FIELDS, f"{name}: expected {sorted(INDEX_FIELDS)}")
        issue_id = entry["issue_id"]
        require(isinstance(issue_id, str) and ISSUE_ID.fullmatch(issue_id), f"{name}: invalid Issue ID")
        require(issue_id.lower() not in normalized_ids, f"{name}: duplicate Issue ID")
        path = f"issues/{issue_id}.yaml"
        require(entry["path"] == path, f"{name}: path must be {path}")
        require(path not in indexed_paths, f"{name}: duplicate path")
        indexed_paths.add(path)
        body_path = ROOT / path
        require(body_path.is_file(), f"{path}: missing Issue body")
        body = read_yaml(body_path.read_text(), path)
        require(body.get("issue_id") == issue_id, f"{path}: issue_id mismatch")
        validate_issue(body, path, earlier)
        for field in ("type", "summary", "attention"):
            require(entry[field] == body[field], f"{name}: {field} differs from {path}")
        if old_index is not None and position < len(old_index):
            previous = from_base(base, path)
            require(previous is not None and body_path.read_bytes() == previous, f"{path}: published Issue files are immutable")
        elif old_index is not None:
            new_changes.append(body)
        earlier.add(issue_id)
        normalized_ids.add(issue_id.lower())

    for path in (ROOT / "issues").glob("*.yaml"):
        relative = path.relative_to(ROOT).as_posix()
        if path.name.startswith("sample-"):
            continue
        require(relative in indexed_paths, f"{relative}: Issue body missing from issues/index.json")

    samples = {}
    for path in sorted((ROOT / "issues").glob("sample-*.yaml")):
        body = read_yaml(path.read_text(), path.name)
        sample_id = body.get("issue_id")
        require(isinstance(sample_id, str) and sample_id.startswith("SAMPLE-"), f"{path.name}: expected SAMPLE- Issue ID")
        require(sample_id not in samples, f"{path.name}: duplicate sample ID")
        validate_issue(body, path.name)
        samples[sample_id] = body
    for sample_id, body in samples.items():
        for reference in body["related_issues"]:
            require(reference in samples, f"{sample_id}: sample may only refer to another sample")

    if base:
        changed = git("diff", "--name-only", base, "--", *GOVERNED)
        untracked = git("ls-files", "--others", "--exclude-standard", "--", *GOVERNED)
        require(changed.returncode == 0 and untracked.returncode == 0, "could not inspect document changes")
        changed_docs = {name for name in (changed.stdout + untracked.stdout).decode().splitlines() if "__pycache__" not in name}
        if old_index is not None:
            declared = {document["file"] for body in new_changes if body["type"] == "DOCUMENT_CHANGE" for document in body["changed_documents"]}
            require(declared <= changed_docs, f"DOCUMENT_CHANGE lists unchanged documents: {sorted(declared - changed_docs)}")
        # Until the first Issue is published, writing the documents is project initialization.
        if old_index:
            require(changed_docs <= declared, f"document changes need new DOCUMENT_CHANGE Issues: {sorted(changed_docs - declared)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base commit SHA for append-only and document-change checks")
    args = parser.parse_args()
    try:
        validate(None if not args.base or set(args.base) == {"0"} else args.base)
    except (ValueError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Shared validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Shared validation passed")
