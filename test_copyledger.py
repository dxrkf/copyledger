import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from copyledger import scan,compare,validate,relative_path,digest_file,outside,write_new,report_html

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'source';self.root.mkdir();(self.root/'a.txt').write_bytes(b'abc');(self.root/'empty').write_bytes(b'')
    def tearDown(self):self.tmp.cleanup()
    def test_exact(self):
        a,issues=scan(self.root);self.assertEqual(issues,[]);self.assertTrue(compare(a,a)['exact_match'])
    def test_same_size_corruption(self):
        a,_=scan(self.root);(self.root/'a.txt').write_bytes(b'xyz');b,_=scan(self.root);self.assertEqual(compare(a,b)['changed'],['a.txt'])
    def test_missing_and_extra(self):
        a,_=scan(self.root);(self.root/'a.txt').unlink();(self.root/'new').write_text('new');b,_=scan(self.root);r=compare(a,b);self.assertEqual(r['missing'],['a.txt']);self.assertEqual(r['extra'],['new'])
    def test_possible_move(self):
        a,_=scan(self.root);(self.root/'a.txt').rename(self.root/'renamed.txt');b,_=scan(self.root);self.assertEqual(compare(a,b)['possible_moves'],[{'before':'a.txt','after':'renamed.txt'}])
    def test_ambiguous_move_not_guessed(self):
        (self.root/'b.txt').write_bytes(b'abc');a,_=scan(self.root);(self.root/'a.txt').unlink();(self.root/'b.txt').unlink();(self.root/'c.txt').write_bytes(b'abc');b,_=scan(self.root);self.assertEqual(compare(a,b)['possible_moves'],[])
    def test_unicode_nested(self):
        (self.root/'مجلد').mkdir();(self.root/'مجلد'/'ملف.txt').write_text('مرحبا');a,_=scan(self.root);self.assertIn('مجلد/ملف.txt',[r['path'] for r in a['files']])
    def test_empty_digest(self):self.assertEqual(digest_file(self.root/'empty')['sha256'],'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
    def test_symlink_not_followed(self):
        if not hasattr(os,'symlink'):self.skipTest('symlinks unsupported')
        target=self.base/'outside.txt';target.write_text('outside');(self.root/'link').symlink_to(target)
        a,issues=scan(self.root);self.assertEqual(len(issues),1);self.assertNotIn('link',[r['path'] for r in a['files']])
    def test_symlink_directory(self):
        (self.root/'dirlink').symlink_to(self.base,target_is_directory=True)
        a,issues=scan(self.root);self.assertEqual(len(issues),1)
    def test_root_symlink_refused(self):
        link=self.base/'linkroot';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):scan(link)
    def test_bad_paths(self):
        for p in ['../x','/x','a/../b','a//b','a/./b','C:x','a\\b','']:
            with self.subTest(path=p):
                with self.assertRaises(ValueError):relative_path(p)
    def test_duplicate_manifest(self):
        a,_=scan(self.root);a['files'].append(a['files'][0])
        with self.assertRaises(ValueError):validate(a)
    def test_invalid_digest(self):
        a,_=scan(self.root);a['files'][0]['sha256']='nope'
        with self.assertRaises(ValueError):validate(a)
    def test_bool_size_rejected(self):
        a,_=scan(self.root);a['files'][0]['bytes']=True
        with self.assertRaises(ValueError):validate(a)
    def test_no_overwrite(self):
        out=self.base/'receipt.json';out.write_text('keep')
        with self.assertRaises(FileExistsError):write_new(out,'changed')
        self.assertEqual(out.read_text(),'keep')
    def test_output_inside_root_refused(self):
        with self.assertRaises(ValueError):outside(self.root,[self.root/'receipt.json'])
    def test_html_escape(self):self.assertNotIn('<script>',report_html({'value':'<script>alert(1)</script>'}))
    def test_cli(self):
        script=str(Path(__file__).with_name('copyledger.py'));receipt=self.base/'receipt.json'
        def run(args):return subprocess.run([sys.executable,script]+list(map(str,args)),capture_output=True,text=True)
        self.assertEqual(run(['receipt',self.root,'--output',receipt]).returncode,0)
        self.assertEqual(run(['verify',receipt,self.root]).returncode,0)
        (self.root/'a.txt').write_bytes(b'xyz');r=run(['verify',receipt,self.root,'--json']);self.assertEqual(r.returncode,1);self.assertEqual(json.loads(r.stdout)['changed'],['a.txt'])
        self.assertEqual(run(['receipt',self.root,'--output',receipt]).returncode,2)

if __name__=='__main__':unittest.main()
