#!/usr/bin/env python3
"""Decide whether a Shared PR only publishes new MESSAGE Issues and may be approved by CI.

Prints eligible=true or eligible=false for $GITHUB_OUTPUT and the reasons to stderr.
"""

import argparse
import sys

import validate_shared as shared


def codeowners_problem(base):
    """Auto-approval is safe only while CODEOWNERS makes every other change need a human."""
    data = shared.from_base(base, ".github/CODEOWNERS")
    if data is None:
        return ".github/CODEOWNERS is missing"
    for line in data.decode().splitlines():
        rule = line.split()
        if rule and rule[0] == "*" and len(rule) > 1 and all(owner.startswith("@") and "<" not in owner for owner in rule[1:]):
            return None
    return ".github/CODEOWNERS needs a real owner for *"


def problems(base):
    shared.validate(base)
    found = []
    problem = codeowners_problem(base)
    if problem:
        found.append(problem)

    changed = shared.git("diff", "--name-status", "--no-renames", base, "HEAD")
    shared.require(changed.returncode == 0, "could not inspect PR changes")
    added = []
    for line in changed.stdout.decode().splitlines():
        status, path = line.split("\t", 1)
        if status == "M" and path == "issues/index.json":
            continue
        issue_id = path.removeprefix("issues/").removesuffix(".yaml")
        if status == "A" and path == f"issues/{issue_id}.yaml" and shared.ISSUE_ID.fullmatch(issue_id):
            added.append(path)
            continue
        found.append(f"{path}: only new Issues and issues/index.json are approved automatically")
    for path in added:
        kind = shared.read_yaml((shared.ROOT / path).read_text(), path).get("type")
        if kind != "MESSAGE":
            found.append(f"{path}: {kind} needs a human review")
    if not added:
        found.append("no new MESSAGE Issue")
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="PR base commit SHA")
    args = parser.parse_args()
    try:
        found = problems(args.base)
    except Exception as exc:  # Any doubt leaves the PR to a human reviewer.
        found = [f"check failed: {exc}"]
    for problem in found:
        print(f"Not approved automatically: {problem}", file=sys.stderr)
    print(f"eligible={'false' if found else 'true'}")
