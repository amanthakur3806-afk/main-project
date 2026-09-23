"""
Knowledge Base & RAG Management API Endpoints
"""
import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.knowledge import KnowledgeBase, Document
from app.schemas.knowledge import KnowledgeBaseResponse, KnowledgeBaseCreate, IngestResponse
from app.rag.ingest import ingest_knowledge_base

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & RAG"])

@router.get("/bases", response_model=List[KnowledgeBaseResponse], summary="List all registered knowledge bases")
def list_knowledge_bases(db: Session = Depends(get_db)):
    bases = db.query(KnowledgeBase).all()
    return bases

@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED, summary="Register a new knowledge base")
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    existing = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == payload.kb_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Knowledge base '{payload.kb_id}' already exists.")

    kb_path = Path(payload.folder_path)
    kb_path.mkdir(parents=True, exist_ok=True)

    kb = KnowledgeBase(
        kb_id=payload.kb_id,
        name=payload.name,
        description=payload.description,
        folder_path=str(kb_path),
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        embedding_model=payload.embedding_model
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb

@router.post("/upload", response_model=IngestResponse, summary="Upload a document and auto-ingest into FAISS + SQL")
async def upload_document(
    kb_id: str = Form(..., description="Target knowledge base ID, e.g. 'customer_docs'"),
    file: UploadFile = File(..., description="Document file to upload (.md, .txt, .pdf, .docx)"),
    db: Session = Depends(get_db)
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found.")

    target_dir = Path(kb.folder_path)
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(file.filename).name
    file_dest = target_dir / safe_filename

    # Save file to disk
    with open(file_dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ingest folder
    ingest_result = ingest_knowledge_base(
        kb_id=kb.kb_id,
        folder_path=str(target_dir),
        db=db,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap
    )

    return IngestResponse(
        kb_id=kb.kb_id,
        documents_ingested=ingest_result["documents_ingested"],
        chunks_created=ingest_result["chunks_created"],
        status="ingested_successfully"
    )

@router.post("/reindex", response_model=IngestResponse, summary="Trigger re-indexing of a knowledge base directory")
def reindex_knowledge_base(
    kb_id: str = Form(..., description="Knowledge base ID to reindex"),
    db: Session = Depends(get_db)
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found.")

    ingest_result = ingest_knowledge_base(
        kb_id=kb.kb_id,
        folder_path=kb.folder_path,
        db=db,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap
    )

    return IngestResponse(
        kb_id=kb.kb_id,
        documents_ingested=ingest_result["documents_ingested"],
        chunks_created=ingest_result["chunks_created"],
        status="reindexed_successfully"
    )
