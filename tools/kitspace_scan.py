#!/usr/bin/env python3
"""Find hardware-fix commits in the projects listed by Kitspace (https://github.com/kitspace/kitspace).

    python3 tools/kitspace_scan.py WORKDIR

Step 1 (not done here): clone the registry and each repository in its boards.txt into
WORKDIR/repos/<owner>__<name> with `git clone --filter=blob:none --no-checkout` (history and file
names only).  Step 2 (this script): read each repository's log and report commits whose subject
looks like a fix and that touch a schematic or board file, plus errata text in READMEs.
Only git output is read; nothing from the repositories is executed.  Writes WORKDIR/scan.json.
"""
import json, os, re, subprocess, sys
K = sys.argv[1]
R = os.path.join(K, 'repos')
KW = re.compile(r"\b(fix(e[sd])?|bug|errata|erratum|wrong|swap(ped)?|mistake|missing|incorrect|oops|forgot|bodge|rework|"
                r"pull-?ups?|pull-?downs?|short(ed)?|polarity|revers(ed|e)|pinout|flipped|mirrored|inverted|"
                r"backwards|typo|broken|doesn'?t work|not work(ing)?|should (be|have)|rev(ision)? ?[b-f2-9]\b)", re.I)
STRONG = re.compile(r"swap|wrong|revers|polarity|pinout|mirrored|flipped|inverted|backwards|errata|bodge|missing pull|"
                    r"pull-?up|pull-?down|short|rx|tx|sda|scl|miso|mosi|footprint|decoupl|mistake|incorrect", re.I)
HW = re.compile(r"\.(kicad_sch|kicad_pcb|sch)$", re.I)

def git(repo, *a, timeout=120):
    try:
        return subprocess.run(['git', '-C', repo, *a], capture_output=True, text=True, timeout=timeout, errors='replace').stdout
    except subprocess.TimeoutExpired:
        return ''

out = []
for name in sorted(os.listdir(R)):
    repo = os.path.join(R, name)
    files = git(repo, 'ls-tree', '-r', '--name-only', 'HEAD').splitlines()
    if not files:
        continue
    has6 = any(f.endswith('.kicad_sch') for f in files)
    pcb = any(f.endswith('.kicad_pcb') for f in files)
    legacy = any(f.endswith('.sch') for f in files) and any(f.endswith(('.pro', '-cache.lib')) for f in files)
    eagle = any(f.endswith('.brd') for f in files)
    fmt = 'kicad6+' if has6 else 'kicad5' if legacy and pcb else 'kicad-pcb-only' if pcb else 'eagle' if eagle else 'other'
    log = git(repo, 'log', '--format=@@%H%x09%ad%x09%an%x09%s', '--date=short', '--name-only')
    commits, cur = [], None
    for ln in log.splitlines():
        if ln.startswith('@@'):
            h, d, an, s = (ln[2:].split('\t') + ['', '', ''])[:4]
            cur = {'sha': h, 'date': d, 'author': an, 'subject': s, 'files': []}
            commits.append(cur)
        elif ln.strip() and cur is not None:
            cur['files'].append(ln.strip())
    cands = []
    for c in commits:
        hw = [f for f in c['files'] if HW.search(f)]
        if hw and KW.search(c['subject']):
            cands.append({'sha': c['sha'], 'date': c['date'], 'subject': c['subject'][:140], 'hw_files': hw[:4],
                          'strong': bool(STRONG.search(c['subject'])), 'n_files': len(c['files'])})
    readme = [f for f in files if re.match(r'^(readme|errata|changelog|changes|history|notes)[^/]*$', f, re.I)]
    errata = []
    for f in readme[:4]:
        txt = git(repo, 'show', f'HEAD:{f}', timeout=60)
        for i, ln in enumerate(txt.splitlines()):
            if re.search(r'errata|known (issues|bugs|problems)|bodge|rework|green wire|mistakes?\b|rev(ision)? ?\w* (fixes|changes)', ln, re.I):
                errata.append(f"{f}:{i + 1}: {ln.strip()[:160]}")
    out.append({'name': name.replace('__', '/'), 'format': fmt, 'commits': len(commits),
                'authors': len({c['author'] for c in commits}), 'last': commits[0]['date'] if commits else '',
                'hw_commits': sum(1 for c in commits if any(HW.search(f) for f in c['files'])),
                'candidates': cands, 'errata_lines': errata[:12]})
json.dump(out, open(os.path.join(K, 'scan.json'), 'w'), indent=1)
from collections import Counter
print(len(out), 'repos;', Counter(o['format'] for o in out))
print('with candidate fix commits:', sum(1 for o in out if o['candidates']), '; with errata text:', sum(1 for o in out if o['errata_lines']))
