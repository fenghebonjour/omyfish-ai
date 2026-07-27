"""
retrieval.py — regs_advisor.engine
--------------------------------------
Single-hop retrieval over the curated knowledge_base/ markdown files: chunk
by section heading, score by TF-IDF cosine similarity. No vector DB and no
embedding model — the corpus is a few dozen sections of domain-keyword-heavy
text (species names, regulation terms), where keyword overlap is a strong
signal and a hand-rolled TF-IDF avoids a new ML dependency + model download
for a corpus this size (see docs/REGS_CHATBOT_PLAN.md "On LangChain").
"""

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

KB_DIR = Path(__file__).parent.parent / "knowledge_base"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Chunk:
    source: str    # filename, e.g. "species_tackle.md"
    heading: str   # section heading, e.g. "Walleye (doré jaune)"
    text: str      # full section body (heading included) sent to the LLM as context


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def load_chunks(kb_dir: Path = KB_DIR) -> list[Chunk]:
    chunks = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Drop the top-level "# Title" line; split the rest on "## " headings.
        body = re.sub(r"^#\s+.*\n", "", text, count=1)
        sections = re.split(r"\n(?=## )", body)
        for section in sections:
            section = section.strip()
            if not section:
                continue
            heading = section.splitlines()[0].removeprefix("## ").strip()
            chunks.append(Chunk(source=path.name, heading=heading, text=section))
    return chunks


class TfidfIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        docs_tokens = [_tokenize(c.text) for c in chunks]
        vocab: dict[str, int] = {}
        for tokens in docs_tokens:
            for t in set(tokens):
                vocab.setdefault(t, len(vocab))
        self.vocab = vocab

        n_docs = len(chunks)
        doc_freq = np.zeros(len(vocab))
        tf_matrix = np.zeros((n_docs, len(vocab)))
        for i, tokens in enumerate(docs_tokens):
            for t in tokens:
                tf_matrix[i, vocab[t]] += 1
            for t in set(tokens):
                doc_freq[vocab[t]] += 1
            if tokens:
                tf_matrix[i] /= len(tokens)

        self.idf = np.log((1 + n_docs) / (1 + doc_freq)) + 1
        self.doc_vectors = tf_matrix * self.idf
        norms = np.linalg.norm(self.doc_vectors, axis=1, keepdims=True)
        self._norm_doc_vectors = self.doc_vectors / np.where(norms == 0, 1, norms)

    def _query_vector(self, query: str) -> np.ndarray:
        vec = np.zeros(len(self.vocab))
        tokens = _tokenize(query)
        for t in tokens:
            idx = self.vocab.get(t)
            if idx is not None:
                vec[idx] += 1
        if tokens:
            vec /= len(tokens)
        return vec * self.idf

    def top_k(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        q = self._query_vector(query)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        scores = self._norm_doc_vectors @ (q / q_norm)
        ranked = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in ranked if scores[i] > 0]


_index: TfidfIndex | None = None


def get_index() -> TfidfIndex:
    global _index
    if _index is None:
        _index = TfidfIndex(load_chunks())
    return _index
