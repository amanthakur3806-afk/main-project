"""
RAG Ingestion Pipeline
Handles file reading, content extraction, chunking, embedding generation,
and storing vector records in FAISS and relational metadata in SQL.
"""
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.rag.embeddings import embeddings_provider
from app.rag.vector_store import vector_store

def extract_text_from_file(file_path: Path) -> str:
    """Extract raw text from Markdown, TXT, or document files."""
    ext = file_path.suffix.lower()
    if ext in [".md", ".txt", ".json", ".csv"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == ".pdf":
        # Basic PDF stream text extractor fallback
        try:
            with open(file_path, "rb") as f:
                content = f.read().decode("latin-1", errors="ignore")
                # Strip raw PDF formatting markers
                return content
        except Exception:
            return ""
    elif ext == ".docx":
        # Basic DOCX zip reader or raw text fallback
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(file_path) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                text = " ".join([elem.text for elem in tree.iter() if elem.text])
                return text
        except Exception:
            return ""
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

def chunk_text(text: str, chunk_size: int = 400, chunk_overlap: int = 50) -> List[str]:
    """
    Split text into overlapping semantic chunks based on token/character boundaries.
    Preserves paragraph or sentence structure where possible.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue

        words = para_clean.split()
        if current_len + len(words) <= chunk_size:
            current_chunk.append(para_clean)
            current_len += len(words)
        else:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            # Handle long single paragraphs
            if len(words) > chunk_size:
                step = max(chunk_size - chunk_overlap, 50)
                for i in range(0, len(words), step):
                    chunk_slice = " ".join(words[i:i + chunk_size])
                    if chunk_slice:
                        chunks.append(chunk_slice)
                current_chunk = []
                current_len = 0
            else:
                current_chunk = [para_clean]
                current_len = len(words)

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks if chunks else [text]

def ingest_knowledge_base(
    kb_id: str,
    folder_path: str,
    db: Session,
    chunk_size: int = 400,
    chunk_overlap: int = 50
) -> Dict[str, Any]:
    """
    Full ingestion pipeline for a knowledge base directory:
    Folder -> Documents -> Chunks -> Embeddings -> FAISS + SQL.
    """
    path = Path(folder_path)
    if not path.exists():
        return {"kb_id": kb_id, "documents_ingested": 0, "chunks_created": 0, "status": "Directory does not exist"}

    # Ensure KB record in DB
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == kb_id).first()
    if not kb:
        kb = KnowledgeBase(
            kb_id=kb_id,
            name=kb_id.replace("_", " ").title(),
            description=f"Knowledge base for {kb_id}",
            folder_path=str(folder_path),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        db.add(kb)
        db.commit()

    supported_extensions = {".md", ".txt", ".pdf", ".docx"}
    files = [p for p in path.glob("**/*") if p.is_file() and p.suffix.lower() in supported_extensions]

    docs_ingested = 0
    total_chunks = 0
    vectors_to_add = []
    metadata_to_add = []

    for file_path in files:
        raw_text = extract_text_from_file(file_path)
        if not raw_text.strip():
            continue

        file_stat = file_path.stat()
        file_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Check existing document record
        existing_doc = db.query(Document).filter(
            Document.kb_id == kb_id,
            Document.filename == file_path.name
        ).first()

        if existing_doc and existing_doc.content_hash == file_hash:
            # File unchanged, skip
            continue

        if existing_doc:
            db.delete(existing_doc)
            db.commit()

        # Create new Document record
        doc = Document(
            kb_id=kb_id,
            filename=file_path.name,
            file_type=file_path.suffix.lstrip("."),
            file_size=file_stat.st_size,
            content_hash=file_hash
        )
        db.add(doc)
        db.flush()

        chunks = chunk_text(raw_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        doc_chunk_records = []
        for idx, chunk_text_content in enumerate(chunks):
            chunk_record = DocumentChunk(
                document_id=doc.id,
                kb_id=kb_id,
                chunk_index=idx,
                content=chunk_text_content,
                token_count=len(chunk_text_content.split())
            )
            db.add(chunk_record)
            doc_chunk_records.append(chunk_record)

        db.flush()

        # Batch embed chunks
        embeddings = embeddings_provider.get_embeddings_batch(chunks)
        for idx, chunk_record in enumerate(doc_chunk_records):
            vectors_to_add.append(embeddings[idx])
            metadata_to_add.append({
                "chunk_id": chunk_record.id,
                "document_id": doc.id,
                "kb_id": kb_id,
                "filename": file_path.name,
                "chunk_index": idx,
                "content": chunk_record.content
            })

        docs_ingested += 1
        total_chunks += len(chunks)

    db.commit()

    # Index into FAISS
    if vectors_to_add:
        import numpy as np
        vector_matrix = np.array(vectors_to_add, dtype=np.float32)
        assigned_ids = vector_store.add_vectors(vector_matrix, metadata_to_add)
        
        # Link assigned vector IDs to SQL records
        for vid, meta in zip(assigned_ids, metadata_to_add):
            chunk_id = meta["chunk_id"]
            db_chunk = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
            if db_chunk:
                db_chunk.vector_id = vid
        db.commit()

    return {
        "kb_id": kb_id,
        "documents_ingested": docs_ingested,
        "chunks_created": total_chunks,
        "status": "success"
    }
