import os
import glob
import math
import json
import asyncio

def _cosine_similarity(v1, v2):
    dot = sum(a*b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a*a for a in v1))
    norm_v2 = math.sqrt(sum(b*b for b in v2))
    if norm_v1 == 0 or norm_v2 == 0: return 0.0
    return dot / (norm_v1 * norm_v2)

class HybridMemoryRAG:
    """
    Motor de Busca Híbrido (Vetorial + Palavra-Chave) para o OpenClaw Parity.
    Utiliza as APIs existentes de embeddings do Gemini/Mistral e cacheia em JSON = zero dep.
    """
    def __init__(self, base_dir: str, workspace_dir: str, get_embedding_func):
        self.base_dir = base_dir
        self.workspace_dir = workspace_dir
        self.get_embedding_func = get_embedding_func
        mem_dir = os.path.join(base_dir, "memory")
        os.makedirs(mem_dir, exist_ok=True)
        self.cache_file = os.path.join(mem_dir, "vectors_cache.json")
        self.vectors = {} # map: chunk_text -> embedding_list
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.vectors = json.load(f)
            except:
                self.vectors = {}

    def save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.vectors, f)
        except: pass

    async def get_embedding_cached(self, text: str):
        text_hash = text.strip()
        if not text_hash: return None
        if text_hash in self.vectors:
            return self.vectors[text_hash]
        
        # O function call ao LLM
        emb = await self.get_embedding_func(text_hash)
        if emb:
            self.vectors[text_hash] = emb
            self.save_cache()
        return emb

    async def search(self, query: str, top_k: int = 5):
        query_emb = await self.get_embedding_cached(query)
        
        mem_dir = os.path.join(self.base_dir, "memory")
        check_files = [os.path.join(self.workspace_dir, "MEMORY.md")] + glob.glob(f"{mem_dir}/*.md")
        
        chunks = []
        # Chunking: Lê arquivos pararágrafo por parágrafo
        for fpath in check_files:
            if not os.path.exists(fpath): continue
            try:
                with open(fpath, "r", encoding="utf-8") as file:
                    content = file.read()
                    blocks = content.split("\n\n") # Parágrafos
                    for i, b in enumerate(blocks):
                        b = b.strip()
                        if b:
                            rel_path = os.path.relpath(fpath, self.workspace_dir)
                            chunks.append({"text": b, "file": rel_path, "block": i})
            except: continue

        results = []
        for c in chunks:
            # BM25 Fallback/Keyword score
            keyword_score = 0.0
            query_lower = query.lower()
            if query_lower in c["text"].lower(): keyword_score = 0.3
            
            # Vector score
            vec_score = 0.0
            if query_emb:
                chunk_emb = await self.get_embedding_cached(c["text"])
                if chunk_emb:
                    vec_score = _cosine_similarity(query_emb, chunk_emb)
                    
            final_score = vec_score + keyword_score
            results.append((final_score, c))
            
        results.sort(key=lambda x: x[0], reverse=True)
        return [r for r in results[:top_k] if r[0] > 0.15] # 0.15 é um threshold de similaridade bom
