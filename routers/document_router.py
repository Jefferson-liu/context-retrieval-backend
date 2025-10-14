from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from services.document.processing import DocumentProcessingService
from services.document.chunk_editing import ChunkEditingService
from services.document.retrieval import DocumentRetrievalService
from infrastructure.context import RequestContextBundle
from routers.dependencies import get_request_context_bundle
from schemas.requests import EditDocumentRequest, EditChunkRequest

router = APIRouter()

@router.post("/upload", summary="Upload and process a document")
async def upload_document(
    file: UploadFile = File(...),
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle)
):
    """
    Upload a file, process it (chunk, embed), and store in the database.
    Supports text/markdown files.
    """
    if not file.filename.endswith(('.txt', '.md')):
        raise HTTPException(status_code=400, detail="Only .txt and .md files are supported")
    
    try:
        content = await file.read()
        text_content = content.decode("utf-8")

        service = DocumentProcessingService(context_bundle.db, context_bundle.scope)
        doc_id = await service.upload_and_process_document(
            content=text_content,
            doc_name=file.filename,
            doc_type=file.content_type or "text/plain"
        )
        
        return {
            "message": "Document uploaded and processed successfully",
            "doc_id": doc_id,
            "chunks_created": len(text_content) // 512  # Approximate
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/documents", summary="List all documents")
async def list_documents(context_bundle: RequestContextBundle = Depends(get_request_context_bundle)):
    """
    Retrieve a list of all uploaded documents.
    """
    service = DocumentRetrievalService(context_bundle.db, context_bundle.scope)
    docs = await service.list_documents()
    return {"documents": [{"id": d.id, "name": d.doc_name, "type": d.doc_type} for d in docs]}

@router.get("/documents/{doc_id}", summary="Get a specific document")
async def get_document(doc_id: int, context_bundle: RequestContextBundle = Depends(get_request_context_bundle)):
    """
    Retrieve details of a specific document by ID.
    """
    service = DocumentRetrievalService(context_bundle.db, context_bundle.scope)
    doc = await service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "name": doc.doc_name,
        "content": doc.content,
        "type": doc.doc_type,
        "upload_date": doc.upload_date
    }

@router.put("/documents/{doc_id}", summary="Update an existing document")
async def edit_document(
    doc_id: int,
    payload: EditDocumentRequest,
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle),
):
    service = DocumentProcessingService(context_bundle.db, context_bundle.scope)
    updated = await service.update_document(
        document_id=doc_id,
        context=payload.content,
        doc_type=payload.doc_type,
        commit_message=payload.commit_message,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document updated successfully", "doc_id": doc_id}

@router.delete("/documents/{doc_id}", summary="Delete a document")
async def delete_document(doc_id: int, context_bundle: RequestContextBundle = Depends(get_request_context_bundle)):
    """
    Delete a document and its associated chunks/embeddings.
    """
    service = DocumentProcessingService(context_bundle.db, context_bundle.scope)
    success = await service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@router.put(
    "/documents/{doc_id}/chunks/{chunk_id}",
    summary="Update a document chunk",
)
async def edit_chunk(
    doc_id: int,
    chunk_id: int,
    payload: EditChunkRequest,
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle),
):
    service = ChunkEditingService(context_bundle.db, context_bundle.scope)
    chunk = await service.update_chunk(
        doc_id,
        chunk_id,
        content=payload.content,
        context_override=payload.context,
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found for document")

    return {
        "chunk_id": chunk.id,
        "doc_id": chunk.doc_id,
        "content": chunk.content,
        "context": chunk.context,
    }