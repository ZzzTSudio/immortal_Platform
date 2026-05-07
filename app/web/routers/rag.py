"""Admin RAG routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.rag.indexer import parse_preprocess_config, source_type_for_filename
from app.rag.models import RAGUploadResponse
from app.web.routers.auth import require_admin

router = APIRouter()


def _rag_runtime(request: Request):
    runtime = getattr(request.app.state, "rag_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="RAG 服务未就绪，请检查 Qdrant 配置")
    return runtime


@router.get("/admin/rag/stats")
async def get_rag_stats(request: Request):
    require_admin(request)
    runtime = _rag_runtime(request)
    documents = await runtime.indexer.list_documents()
    skills: dict[str, dict] = {}
    total_chunks = 0
    for doc in documents:
        skill_id = str(doc.get("skill_id") or "")
        chunk_count = int(doc.get("chunk_count") or 0)
        total_chunks += chunk_count
        item = skills.setdefault(
            skill_id,
            {
                "skill_id": skill_id,
                "doc_count": 0,
                "chunk_count": 0,
                "documents": [],
            },
        )
        item["doc_count"] += 1
        item["chunk_count"] += chunk_count
        item["documents"].append(doc)
    return {
        "collection": runtime.settings.qdrant_collection,
        "mode": runtime.settings.qdrant_mode,
        "total_documents": len(documents),
        "total_chunks": total_chunks,
        "skills": list(skills.values()),
    }


@router.delete("/admin/rag/documents/{skill_id}/{doc_id}")
async def delete_rag_document(request: Request, skill_id: str, doc_id: str):
    require_admin(request)
    runtime = _rag_runtime(request)
    deleted_chunks = await runtime.indexer.delete_document(skill_id=skill_id, doc_id=doc_id)
    if deleted_chunks <= 0:
        raise HTTPException(status_code=404, detail="未找到对应文档向量")
    return {
        "success": True,
        "skill_id": skill_id,
        "doc_id": doc_id,
        "deleted_chunks": deleted_chunks,
    }


@router.get("/admin/rag/documents/{skill_id}/{doc_id}/chunks")
async def get_rag_document_chunks(request: Request, skill_id: str, doc_id: str):
    require_admin(request)
    runtime = _rag_runtime(request)
    chunks = await runtime.indexer.list_document_chunks(skill_id=skill_id, doc_id=doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="未找到对应文档分块")
    return {
        "skill_id": skill_id,
        "doc_id": doc_id,
        "chunks": chunks,
    }


@router.post("/admin/rag/upload")
async def upload_rag_files(
    request: Request,
    target_skill_id: str = Form(...),
    preprocess_config: str | None = Form(None),
    files: list[UploadFile] = File(...),
):
    require_admin(request)
    runtime = _rag_runtime(request)

    skill_id = target_skill_id.strip()
    if not skill_id:
        raise HTTPException(status_code=400, detail="target_skill_id 不能为空")
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    try:
        config = parse_preprocess_config(preprocess_config)
        payload_files: list[tuple[str, bytes]] = []
        for file in files:
            filename = file.filename or ""
            source_type_for_filename(filename)
            payload_files.append((filename, await file.read()))
        indexed = await runtime.indexer.index_files(
            skill_id=skill_id,
            files=payload_files,
            preprocess_config=config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG 上传处理失败：{exc}") from exc

    return RAGUploadResponse(
        target_skill_id=skill_id,
        files=indexed,
        total_chunks=sum(item.chunks for item in indexed),
    )

