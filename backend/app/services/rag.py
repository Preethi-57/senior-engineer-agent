from pathlib import Path
import re
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer=None; cosine_similarity=None

class RAGIndex:
    """Local retrieval index. Files are chunked so retrieval is evidence-local and
    does not require shipping an entire repository to the model."""
    def __init__(self,root:Path,files:list[Path],max_bytes=500000,chunk_lines=80):
        self.root=root; self.docs=[]; self.vectorizer=None; self.matrix=None
        allowed={'.py','.js','.ts','.tsx','.jsx','.java','.go','.rs','.yaml','.yml','.json','.toml','.md','.txt','.sql','.xml','.ini','.cfg','.conf'}
        for p in files:
            if p.suffix.lower() not in allowed: continue
            try:text=p.read_bytes()[:max_bytes].decode('utf-8',errors='replace')
            except Exception:continue
            lines=text.splitlines()
            for start in range(0,len(lines),chunk_lines):
                chunk='\n'.join(lines[start:start+chunk_lines])
                if len(chunk.strip())<20: continue
                self.docs.append((str(p.relative_to(root)),start+1,chunk))
        if TfidfVectorizer and self.docs:
            self.vectorizer=TfidfVectorizer(token_pattern=r'(?u)\b[A-Za-z_][A-Za-z0-9_./:-]{1,}\b',max_features=100000)
            self.matrix=self.vectorizer.fit_transform([x[2] for x in self.docs])
    def search(self,query,k=8):
        if not self.docs:return []
        if self.vectorizer:
            scores=cosine_similarity(self.vectorizer.transform([query]),self.matrix)[0]; ids=scores.argsort()[::-1][:k]
            return [{'path':self.docs[i][0],'start_line':self.docs[i][1],'score':float(scores[i]),'snippet':self.docs[i][2][:3500]} for i in ids if scores[i]>0]
        terms=set(re.findall(r'\w+',query.lower())); scored=[]
        for path,line,text in self.docs: scored.append((sum(text.lower().count(t) for t in terms),path,line,text))
        return [{'path':p,'start_line':line,'score':float(s),'snippet':t[:3500]} for s,p,line,t in sorted(scored,reverse=True)[:k] if s]
    def context(self,results,max_chars=12000):
        chunks=[]; used=0
        for item in results:
            block=f"FILE: {item['path']}\nSTART_LINE: {item.get('start_line',1)}\nSCORE: {item['score']:.4f}\n{item['snippet']}\n"
            if used+len(block)>max_chars:break
            chunks.append(block);used+=len(block)
        return '\n---\n'.join(chunks)
