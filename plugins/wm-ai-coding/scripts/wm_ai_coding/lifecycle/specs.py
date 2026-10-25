"""Deterministic requirement-block deltas with preserved, checked preimages."""
from __future__ import annotations

import re
from pathlib import Path


def read_tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(root.rglob("*.md")) if p.is_file()} if root.is_dir() else {}


def blocks(text: str) -> tuple[str, dict[str, str]]:
    matches = list(re.finditer(r"(?m)^### Requirement:\s*(\S[^\n]*)\n?", text))
    result = {}
    for i, match in enumerate(matches):
        key = match[1].strip()
        if key in result:
            raise ValueError(f"duplicate requirement: {key}")
        result[key] = text[match.start():matches[i+1].start() if i+1 < len(matches) else len(text)].strip() + "\n"
    return text[:matches[0].start()] if matches else text, result


def expected_specs(before: dict[str, str], deltas: dict[str, str]) -> dict[str, str]:
    expected = dict(before)
    for path, delta in deltas.items():
        header, requirements = blocks(before.get(path, ""))
        if path not in before:
            header = f"# {Path(path).parent.as_posix()} Specification\n\n## Requirements\n\n"
        operations = list(re.finditer(r"(?m)^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements\s*$", delta))
        if not operations:
            raise ValueError(f"delta needs explicit operations: {path}")
        touched = set()
        for i, match in enumerate(operations):
            section = delta[match.end():operations[i+1].start() if i+1 < len(operations) else len(delta)]
            op = match[1]
            if op == "RENAMED":
                pairs = re.findall(r"(?m)^- FROM: `### Requirement: ([^`]+)`\s*\n- TO: `### Requirement: ([^`]+)`", section)
                if not pairs:
                    raise ValueError("RENAMED needs FROM/TO pairs")
                for old, new in pairs:
                    if old not in requirements or new in requirements:
                        raise ValueError("rename preimage missing or target already exists")
                    body = requirements.pop(old)
                    requirements[new] = body.replace(f"### Requirement: {old}", f"### Requirement: {new}", 1)
            else:
                _, changes = blocks(section)
                if not changes:
                    raise ValueError(f"empty {op} requirements")
                for name, body in changes.items():
                    if name in touched:
                        raise ValueError(f"conflicting delta: {name}")
                    touched.add(name)
                    if op == "ADDED":
                        if name in requirements:
                            raise ValueError(f"ADDED already exists: {name}")
                        requirements[name] = body
                    elif op == "MODIFIED":
                        if name not in requirements:
                            raise ValueError(f"MODIFIED preimage missing: {name}")
                        requirements[name] = body
                    else:
                        if name not in requirements:
                            raise ValueError(f"REMOVED preimage missing: {name}")
                        del requirements[name]
        if requirements:
            expected[path] = header.rstrip() + "\n" + "\n".join(requirements.values())
        else:
            expected.pop(path, None)
    return expected


def normalize(tree: dict[str, str]) -> dict[str, str]:
    return {key: text.replace("\r\n", "\n").strip() for key, text in tree.items()}


def validate_sync(before: dict, deltas: dict, actual: dict) -> list[str]:
    try:
        expected = normalize(expected_specs(before, deltas))
        current = normalize(actual)
        return [f"spec transform mismatch: {p}" for p in sorted(expected.keys() | current.keys())
                if expected.get(p) != current.get(p)]
    except ValueError as exc:
        return [str(exc)]
