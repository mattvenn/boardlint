#!/usr/bin/env python3
"""Historical-bug regression: run boardlint before and after a known fix commit.

    python3 tools/regress.py WORKDIR [id ...]

For each entry of tests/corpus.yaml: clone the repository into WORKDIR (blobless), check out the
parent and the fix into separate directories, run boardlint on both, and print the errors and
warnings that exist only before the fix.  The checked-out projects are third-party data: they are
only parsed, never executed, and boardlint is run with `python3 -I`.
"""
import json
import os
import subprocess
import sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


def sh(*a, cwd=None, timeout=600):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def checkout(work, e, which):
    name = e['repo'].rstrip('/').split('/')[-2] + '_' + e['repo'].rstrip('/').split('/')[-1]
    clone = os.path.join(work, 'clones', name)
    if not os.path.isdir(clone):
        os.makedirs(os.path.dirname(clone), exist_ok=True)
        r = sh('git', 'clone', '--filter=blob:none', '--no-checkout', e['repo'], clone)
        if r.returncode:
            return None, r.stderr.strip()[-200:]
    dst = os.path.join(work, 'trees', f"{e['id']}-{which}")
    if not os.path.isdir(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = sh('git', 'worktree', 'add', '--detach', dst, e[which], cwd=clone)
        if r.returncode:
            return None, r.stderr.strip()[-200:]
    return dst, ''


def lint(tree, project, extra=()):
    r = sh(sys.executable, '-I', '-m', 'boardlint', 'check', os.path.join(tree, project), '-f', 'json', *extra,
           cwd=os.path.dirname(HERE), timeout=600)
    try:
        return json.loads(r.stdout), ''
    except json.JSONDecodeError:
        return None, (r.stderr or r.stdout).strip()[-400:]


def main():
    work = os.path.abspath(sys.argv[1])
    only = set(sys.argv[2:])
    corpus = yaml.safe_load(open(os.path.join(HERE, '..', 'tests', 'corpus.yaml')))
    caught = total = 0
    for e in corpus:
        if only and e['id'] not in only:
            continue
        total += 1
        print(f"\n== {e['id']}: {e['bug']}\n   {e['repo']}  {e['parent'][:9]} -> {e['fix'][:9]}")
        res = {}
        for which in ('parent', 'fix'):
            tree, err = checkout(work, e, which)
            if not tree:
                print(f"   checkout of {which} failed: {err}")
                break
            rep, err = lint(tree, e['project'], e.get('args') or ())
            if rep is None:
                print(f"   boardlint failed on {which}: {err}")
                break
            res[which] = rep
        if len(res) < 2:
            continue
        key = lambda f: (f['check'], f['title'])
        after = {key(f) for f in res['fix']['findings']}
        gone = [f for f in res['parent']['findings'] if key(f) not in after and f['severity'] != 'info']
        new = [f for f in res['fix']['findings'] if key(f) not in {key(g) for g in res['parent']['findings']} and f['severity'] != 'info']
        hit = [f for f in gone if f['check'] in e['expect']]
        for which in ('parent', 'fix'):
            s = res[which]['summary']
            crashed = [c['id'] for c in res[which]['checks'] if c['status'] == 'crashed']
            print(f"   {which:6}: {s.get('error', 0)} errors, {s.get('warning', 0)} warnings, {s.get('info', 0)} notes"
                  + (f"  CRASHED: {crashed}" if crashed else ''))
        for f in gone:
            print(f"   {'*' if f in hit else ' '} only before the fix: {f['severity']} [{f['check']}] {f['title']}")
        for f in new:
            print(f"     only after the fix:  {f['severity']} [{f['check']}] {f['title']}")
        print(f"   {'CAUGHT' if hit else 'MISSED'} (expected one of {e['expect']})"
              + ('' if hit or e.get('detectable', True) else '  [not detectable from the design files alone]'))
        caught += bool(hit)
    print(f"\n{caught} of {total} historical bugs flagged before the fix and cleared by it")


if __name__ == '__main__':
    main()
