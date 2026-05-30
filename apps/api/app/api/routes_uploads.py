import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_authorized_user_context
from app.db.session import get_db_session
from app.domain.sources.schemas import UploadPresignRequest, UploadPresignResponse
from app.domain.sources.service import create_upload_request, store_local_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presign", response_model=UploadPresignResponse)
async def presign_upload(
    payload: UploadPresignRequest,
    session: AsyncSession = Depends(get_db_session),
    context: CurrentUserContext = Depends(get_authorized_user_context),
) -> UploadPresignResponse:
    try:
        source, upload_url = await create_upload_request(session, payload, tenant_id=context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadPresignResponse(
        source_id=source.id,
        object_key=source.object_key,
        upload_url=upload_url,
    )


@router.put("/local/{source_id}", name="upload_local_source", status_code=204)
async def upload_local_source(
    source_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        await store_local_upload(
            session,
            source_id=source_id,
            payload=await request.body(),
            content_type=request.headers.get("content-type", ""),
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Source not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return Response(status_code=204)
