#!/usr/bin/env python3
"""Shared profile loading + background noise generation."""
import json, os, glob, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROF_DIR = os.path.join(ROOT, "profiles")


def list_profiles():
    idx = os.path.join(PROF_DIR, "_index.json")
    if os.path.exists(idx):
        return json.load(open(idx))
    out = []
    for p in sorted(glob.glob(os.path.join(PROF_DIR, "*.json"))):
        if os.path.basename(p).startswith("_"):
            continue
        d = json.load(open(p))
        out.append({"name": d["name"], "dbc": d["dbc"],
                    "score": d.get("score", 0),
                    "coverage": d.get("coverage", [])})
    return out


def load_profile(name):
    p = os.path.join(PROF_DIR, name + ".json")
    if not os.path.exists(p):
        avail = [x["name"] for x in list_profiles()]
        near = [a for a in avail if name.lower() in a.lower()]
        hint = f" Did you mean: {', '.join(near[:5])}?" if near else ""
        raise SystemExit(f"[!] no profile '{name}'.{hint}\n"
                         f"    list them with: ./run.sh --list")
    return json.load(open(p))


def resolve(name):
    """Accept partial names: 'prius' -> toyota_prius_2010_pt."""
    names = [x["name"] for x in list_profiles()]
    if name in names:
        return name
    hits = [n for n in names if name.lower() in n.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        exact = [h for h in hits if h.lower().startswith(name.lower())]
        if len(exact) == 1:
            return exact[0]
        raise SystemExit(f"[!] '{name}' is ambiguous: {', '.join(hits[:8])}")
    return name
