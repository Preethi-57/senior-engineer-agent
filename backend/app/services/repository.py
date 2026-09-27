from __future__ import annotations
import ast
from pathlib import Path

class RepositoryModel:
    """Lightweight language-aware repository graph used as deterministic evidence."""
    def __init__(self,root:Path,files:list[Path]):
        self.root=root; self.files=files; self.nodes=[]; self.edges=[]; self._build()
    def _build(self):
        py={str(p.relative_to(self.root)).replace('/','.')[:-3]:str(p.relative_to(self.root)) for p in self.files if p.suffix=='.py' and p.name!='__init__.py'}
        for p in self.files:
            rel=str(p.relative_to(self.root)); self.nodes.append(rel)
            if p.suffix!='.py': continue
            try: tree=ast.parse(p.read_text(errors='replace'))
            except Exception: continue
            src=rel.replace('/','.').rsplit('.py',1)[0]
            for n in ast.walk(tree):
                mod=None
                if isinstance(n,ast.Import):
                    for a in n.names: mod=a.name
                elif isinstance(n,ast.ImportFrom): mod=n.module
                if mod and mod in py: self.edges.append((rel,py[mod]))
    def summary(self):
        degree={n:0 for n in self.nodes}
        for a,b in self.edges: degree[a]=degree.get(a,0)+1
        return {'nodes':len(self.nodes),'edges':len(self.edges),'top_importers':sorted(degree.items(),key=lambda x:x[1],reverse=True)[:10]}
