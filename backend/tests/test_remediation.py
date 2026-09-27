from pathlib import Path
from app.services.remediation import RemediationEngine
from app.models.domain import Finding, FixProposal, Category, Severity

def test_shell_fix_applies(tmp_path):
    p=tmp_path/'app.py'; p.write_text("import subprocess\nsubprocess.run(cmd, shell=True)\n")
    f=Finding(id='1',category=Category.SECURITY,severity=Severity.HIGH,title='Shell command execution enabled',description='x',files=['app.py'])
    out=RemediationEngine(tmp_path).apply(f,FixProposal(finding_id='1',summary='x',rationale='x'))
    assert out['applied'] and 'shell=False' in p.read_text()

def test_secret_fix_applies(tmp_path):
    p=tmp_path/'app.py'; p.write_text('API_KEY = "real-secret-value"\n')
    f=Finding(id='1',category=Category.SECURITY,severity=Severity.HIGH,title='Hardcoded credential-like value',description='x',files=['app.py'])
    out=RemediationEngine(tmp_path).apply(f,FixProposal(finding_id='1',summary='x',rationale='x'))
    assert out['applied'] and 'os.getenv' in p.read_text()
