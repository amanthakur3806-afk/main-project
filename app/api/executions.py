"""
Execution Observability & Trace API Endpoints
"""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.execution import Execution
from app.schemas.execution import ExecutionTraceResponse, ExecutionStepResponse

router = APIRouter(prefix="/executions", tags=["Executions & Observability"])

@router.get("/{execution_id}", response_model=ExecutionTraceResponse, summary="Get full execution details and timeline")
def get_execution(execution_id: str, db: Session = Depends(get_db)):
    execution = db.query(Execution).filter(Execution.execution_id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    steps = [
        ExecutionStepResponse(
            step_number=s.step_number,
            step_name=s.step_name,
            tool_name=s.tool_name,
            input_payload=s.input_payload,
            output_payload=s.output_payload,
            duration_ms=s.duration_ms,
            status=s.status,
            error_message=s.error_message,
            created_at=s.created_at
        )
        for s in execution.steps
    ]

    return ExecutionTraceResponse(
        execution_id=execution.execution_id,
        agent_id=execution.agent_id,
        conversation_id=execution.conversation_id,
        query=execution.query,
        final_answer=execution.final_answer,
        status=execution.status,
        duration_ms=execution.duration_ms,
        prompt_file_path=execution.prompt_file_path,
        created_at=execution.created_at,
        steps=steps
    )

@router.get("/{execution_id}/trace", summary="Get lightweight step execution trace")
def get_execution_trace(execution_id: str, db: Session = Depends(get_db)):
    execution = db.query(Execution).filter(Execution.execution_id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    trace_records = []
    for s in execution.steps:
        trace_records.append({
            "step": s.step_number,
            "action": s.step_name,
            "tool": s.tool_name,
            "duration_ms": s.duration_ms,
            "status": s.status,
            "error": s.error_message,
            "timestamp": s.created_at.isoformat()
        })

    return {
        "execution_id": execution.execution_id,
        "agent_id": execution.agent_id,
        "total_duration_ms": execution.duration_ms,
        "status": execution.status,
        "trace": trace_records
    }

@router.get("/{execution_id}/prompt", response_class=PlainTextResponse, summary="Download raw final_prompt.txt audit log")
def get_execution_prompt(execution_id: str, db: Session = Depends(get_db)):
    execution = db.query(Execution).filter(Execution.execution_id == execution_id).first()
    if not execution or not execution.prompt_file_path:
        raise HTTPException(status_code=404, detail=f"Prompt log not found for execution '{execution_id}'.")

    prompt_path = Path(execution.prompt_file_path)
    if not prompt_path.exists():
        raise HTTPException(status_code=404, detail="Prompt audit file not found on disk.")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
