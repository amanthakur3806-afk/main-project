import pytest
from app.rag.embeddings import embeddings_provider
from app.rag.vector_store import vector_store
from app.rag.ingest import chunk_text

def test_chunking_logic():
    sample_text = "Paragraph 1 is here.\n\nParagraph 2 is here.\n\nParagraph 3 is here."
    chunks = chunk_text(sample_text, chunk_size=10, chunk_overlap=2)
    assert len(chunks) >= 2

def test_embeddings_generation():
    text = "Customer ABC logistics infrastructure"
    vec = embeddings_provider.get_embedding(text)
    assert vec is not None
    assert len(vec) == 384

def test_faiss_search_and_kb_isolation():
    # Query for customer ABC in customer_docs
    q_vec = embeddings_provider.get_embedding("telemetry webhooks and customer ABC")
    results = vector_store.search(q_vec, top_k=3, kb_id="customer_docs")
    
    assert len(results) > 0
    # Verify all returned chunks belong to the requested knowledge base
    for r in results:
        assert r["kb_id"] == "customer_docs"

    # Verify technical_docs isolation
    tech_results = vector_store.search(q_vec, top_k=3, kb_id="technical_docs")
    for r in tech_results:
        assert r["kb_id"] == "technical_docs"
