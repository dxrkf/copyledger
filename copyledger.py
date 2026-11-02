#!/usr/bin/env python3
"""Read-only folder content receipts and copy verification. Standard library only."""
import argparse
import hashlib
import html
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath


def relative_path(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('unsupported relative path')
    path=PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix()!=value or value=='.':
        raise ValueError('noncanonical relative path')
    return value


def digest_file(path):
    flags=os.O_RDONLY | getattr(os,'O_BINARY',0) | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0)
    fd=os.open(path,flags)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):raise ValueError('not a regular file')
        digest=hashlib.sha256();size=0
        while True:
            block=stream.read(1024*1024)
            if not block:break
            digest.update(block);size+=len(block)
        after=os.fstat(stream.fileno())
    attrs=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
    if size!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in attrs):
        raise ValueError('file changed while hashing')
    return dict(bytes=size,sha256=digest.hexdigest())


def scan(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('root must be an existing nonsymlink directory')
    root=root.resolve();files=[];issues=[]
    def failed(error):raise error
    for parent,dirs,names in os.walk(root,topdown=True,followlinks=False,onerror=failed):
        for name in sorted(dirs.copy()):
            path=Path(parent)/name
            if path.is_symlink():
                issues.append(dict(path=path.relative_to(root).as_posix(),reason='symlink directory not followed'));dirs.remove(name)
        dirs.sort()
        for name in sorted(names):
            path=Path(parent)/name;rel=path.relative_to(root).as_posix()
            try:
                relative_path(rel)
                if path.is_symlink():raise ValueError('symlink file not followed')
                path.resolve().relative_to(root)
                if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('not a regular file')
                item=digest_file(path)
                files.append(dict(path=rel,**item))
            except (OSError,ValueError):
                issues.append(dict(path=rel,reason='unreadable, unsupported, linked or changing file'))
    return dict(format='copyledger-v1',algorithm='sha256',files=sorted(files,key=lambda f:f['path'])),issues


def validate(receipt):
    if not isinstance(receipt,dict) or set(receipt)!={'format','algorithm','files'} or receipt['format']!='copyledger-v1' or receipt['algorithm']!='sha256' or not isinstance(receipt['files'],list):
        raise ValueError('invalid receipt schema')
    seen=set()
    for row in receipt['files']:
        if not isinstance(row,dict) or set(row)!={'path','bytes','sha256'}:raise ValueError('invalid file entry')
        path=relative_path(row['path'])
        if path in seen:raise ValueError('duplicate receipt path')
        seen.add(path)
        if type(row['bytes']) is not int or row['bytes']<0 or not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('invalid size or SHA256')
    return {r['path']:r for r in receipt['files']}


def compare(expected,actual,issues=None):
    old=validate(expected);new=validate(actual)
    missing=sorted(old.keys()-new.keys());extra=sorted(new.keys()-old.keys())
    changed=sorted(k for k in old.keys()&new.keys() if (old[k]['bytes'],old[k]['sha256'])!=(new[k]['bytes'],new[k]['sha256']))
    matched=len(old.keys()&new.keys())-len(changed)
    groups={}
    for kind,paths,source in [('from',missing,old),('to',extra,new)]:
        for path in paths:
            row=source[path];group=groups.setdefault((row['bytes'],row['sha256']),{'from':[],'to':[]});group[kind].append(path)
    moved=[dict(before=g['from'][0],after=g['to'][0]) for _,g in sorted(groups.items()) if len(g['from'])==len(g['to'])==1]
    # Missing/extra entries remain visible even if there is a possible move.
    return dict(format='copyledger-report-v1',matched=matched,missing=missing,changed=changed,extra=extra,possible_moves=moved,scan_issues=issues or [],exact_match=not(missing or changed or extra or issues))


def report_html(report):
    details=html.escape(json.dumps(report,indent=2,ensure_ascii=False))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>CopyLedger review</title><style>body{background:#101827;color:#e2e8f0;font:17px system-ui;max-width:1000px;margin:50px auto;padding:24px}h1{color:#5eead4}pre{background:#1c2a40;border-radius:16px;padding:24px;white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>CopyLedger / copy verification</h1><p>Read-only comparison of regular file bytes and relative paths. Possible moves require review.</p><pre>''' +details+'</pre></html>'


def outside(root,paths):
    root=Path(root).resolve();resolved=[]
    for value in paths:
        if not value:continue
        path=Path(value)
        if path.resolve().is_relative_to(root):raise ValueError('output must be outside the scanned directory')
        if path.exists() or path.is_symlink():raise ValueError('output already exists')
        resolved.append(path.resolve())
    if len(resolved)!=len(set(resolved)):raise ValueError('output paths must be distinct')


def write_new(path,text):
    with Path(path).open('x',encoding='utf-8',newline='') as f:f.write(text)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('receipt');create.add_argument('folder');create.add_argument('--output',required=True)
    check=sub.add_parser('verify');check.add_argument('receipt');check.add_argument('folder');check.add_argument('--json',action='store_true');check.add_argument('--html')
    args=p.parse_args()
    try:
        if args.command=='receipt':
            outside(args.folder,[args.output]);receipt,issues=scan(args.folder)
            if issues:raise ValueError('scan incomplete: '+str(len(issues))+' unsupported/unreadable entries; no receipt written')
            write_new(args.output,json.dumps(receipt,indent=2,ensure_ascii=True)+'\n')
            print(f"Created receipt: {len(receipt['files'])} files, {sum(f['bytes'] for f in receipt['files'])} bytes. Source unchanged.");return 0
        outside(args.folder,[args.html]);expected=json.loads(Path(args.receipt).read_text(encoding='utf-8-sig'));validate(expected)
        actual,issues=scan(args.folder);report=compare(expected,actual,issues)
        if args.html:write_new(args.html,report_html(report))
        if args.json:print(json.dumps(report,indent=2,ensure_ascii=True))
        else:
            print(f"CopyLedger: {report['matched']} matched, {len(report['missing'])} missing, {len(report['changed'])} changed, {len(report['extra'])} extra")
            for field in ('missing','changed','extra'):
                for path in report[field]:print(field.upper()+': '+json.dumps(path,ensure_ascii=True))
            for move in report['possible_moves']:print('POSSIBLE_MOVE: '+json.dumps(move,ensure_ascii=True))
            print(f"Scan issues: {len(issues)}. Files were not modified.")
        return 2 if issues else int(not report['exact_match'])
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print('error: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
