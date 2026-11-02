"""Create synthetic copy mistakes in a temporary folder; run the actual CLI."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from copyledger import scan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--html');p.add_argument('--json',action='store_true');args=p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        base=Path(d);source=base/'source';target=base/'copy';source.mkdir();target.mkdir()
        original={'notes.txt':b'Project notes\n','report.txt':b'PASS','missing.txt':b'Not copied\n','unchanged.txt':b'Same content\n'}
        copied={'renamed-notes.txt':original['notes.txt'],'report.txt':b'FAIL','unchanged.txt':original['unchanged.txt'],'extra.txt':b'Unexpected\n'}
        for name,data in original.items():(source/name).write_bytes(data)
        for name,data in copied.items():(target/name).write_bytes(data)
        receipt,issues=scan(source)
        if issues:raise RuntimeError('unexpected demo scan issue')
        manifest=base/'receipt.json';manifest.write_text(json.dumps(receipt),encoding='utf-8')
        command=[sys.executable,str(Path(__file__).with_name('copyledger.py')),'verify',str(manifest),str(target)]
        if args.json:command.append('--json')
        if args.html:command.extend(['--html',str(Path(args.html).resolve())])
        result=subprocess.run(command,capture_output=True,text=True)
        print(result.stdout,end='')
        if result.stderr:print(result.stderr,end='',file=sys.stderr)
        return 0 if result.returncode==1 else 2

if __name__=='__main__':sys.exit(main())
