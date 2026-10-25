"""Local commits are tested only in disposable repositories."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/code-commit/scripts/commit.py'


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Commit Test')
        self.git('config', 'user.email', 'commit-test@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        (self.repo/'selected.txt').write_text('original\n')
        (self.repo/'unrelated.txt').write_text('original\n')
        self.git('add', '--', 'selected.txt', 'unrelated.txt')
        self.git('commit', '-qm', 'initial')
        self.before=self.git('rev-parse','HEAD')
        (self.repo/'selected.txt').write_text('changed\n')

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],text=True).strip()

    def helper(self,*flags,check=None):
        result=subprocess.run([sys.executable,str(SCRIPT),'--repo',str(self.repo),
            '--files','selected.txt','--message','Update selected',*flags,
            '--check',*(check or [sys.executable,'-c','pass'])],capture_output=True,text=True,timeout=30)
        return result

    def test_preview_runs_checks_without_staging_or_committing(self):
        result=self.helper()
        self.assertEqual(0,result.returncode,result.stderr+result.stdout)
        self.assertEqual('preview',json.loads(result.stdout)['status'])
        self.assertEqual(self.before,self.git('rev-parse','HEAD'))
        self.assertEqual('',self.git('diff','--cached','--name-only'))

    def test_execute_requires_existing_authorization_reference(self):
        result=self.helper('--execute')
        self.assertNotEqual(0,result.returncode)
        self.assertEqual(self.before,self.git('rev-parse','HEAD'))
        self.assertEqual('',self.git('diff','--cached','--name-only'))

    def test_authorized_commit_contains_only_selected_file(self):
        result=self.helper('--execute','--authorization-reference','test:user-local-commit')
        self.assertEqual(0,result.returncode,result.stderr+result.stdout)
        self.assertEqual(['selected.txt'],json.loads(result.stdout)['files'])
        self.assertNotEqual(self.before,self.git('rev-parse','HEAD'))
        self.assertEqual('selected.txt',self.git('diff-tree','--no-commit-id','--name-only','-r','HEAD'))
        self.assertEqual('',self.git('remote'))

    def test_unrelated_staged_changes_are_preserved_and_block_commit(self):
        (self.repo/'unrelated.txt').write_text('user work\n');self.git('add','unrelated.txt')
        index=self.git('diff','--cached','--binary')
        result=self.helper('--execute','--authorization-reference','test:user-local-commit')
        self.assertNotEqual(0,result.returncode)
        self.assertEqual(index,self.git('diff','--cached','--binary'))
        self.assertEqual(self.before,self.git('rev-parse','HEAD'))

    def test_failing_check_does_not_stage_or_commit(self):
        result=self.helper('--execute','--authorization-reference','test:user-local-commit',
                           check=[sys.executable,'-c','raise SystemExit(1)'])
        self.assertNotEqual(0,result.returncode)
        self.assertEqual(self.before,self.git('rev-parse','HEAD'))
        self.assertEqual('',self.git('diff','--cached','--name-only'))

    def test_source_mutating_check_requires_review_before_commit(self):
        result=self.helper('--execute','--authorization-reference','test:user-local-commit',
            check=[sys.executable,'-c',"from pathlib import Path; Path('selected.txt').write_text('mutated')"])
        self.assertNotEqual(0,result.returncode)
        self.assertEqual(self.before,self.git('rev-parse','HEAD'))
        self.assertEqual('',self.git('diff','--cached','--name-only'))

    def test_hook_expanded_commit_is_reported_without_resetting_user_work(self):
        hook=self.repo/'.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nprintf "hook change\\n" > unrelated.txt\ngit add -- unrelated.txt\n')
        hook.chmod(0o755)
        result=self.helper('--execute','--authorization-reference','test:user-local-commit')
        self.assertNotEqual(0,result.returncode)
        data=json.loads(result.stdout)
        self.assertEqual('scope_exceeded',data['status'])
        self.assertIn('unrelated.txt',data['files'])
        self.assertNotEqual(self.before,self.git('rev-parse','HEAD'))
