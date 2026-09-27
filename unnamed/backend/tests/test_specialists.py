from pathlib import Path
from app.agents.specialists import SecurityAgent,ScalabilityAgent,ReliabilityAgent
from app.services.rag import RAGIndex

def make(tmp_path, code):
    p=tmp_path/"app.py"; p.write_text(code); return tmp_path

def test_security_detects_eval(tmp_path):
    root=make(tmp_path,"def x(v):\n    eval(v)\n")
    fs=SecurityAgent(root,RAGIndex(root,[root/"app.py"])).analyze()
    assert any("Dynamic code execution" in f.title for f in fs)

def test_security_detects_shell(tmp_path):
    root=make(tmp_path,"import subprocess\nsubprocess.run('x', shell=True)\n")
    fs=SecurityAgent(root,RAGIndex(root,[root/"app.py"])).analyze()
    assert any("Shell command" in f.title for f in fs)

def test_scalability_loop_io(tmp_path):
    root=make(tmp_path,"for x in xs:\n    db.execute('select 1')\n")
    fs=ScalabilityAgent(root,RAGIndex(root,[root/"app.py"])).analyze()
    assert any("N+1" in f.title for f in fs)

def test_reliability_bare_except(tmp_path):
    root=make(tmp_path,"try:\n    x()\nexcept:\n    pass\n")
    fs=ReliabilityAgent(root,RAGIndex(root,[root/"app.py"])).analyze()
    assert any("Bare exception" in f.title for f in fs)
