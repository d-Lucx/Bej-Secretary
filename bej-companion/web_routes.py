"""Isolated capture routes; extension requests cannot reach workspace APIs."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from web_notes import DESTINATION

EXTENSION_PATHS = {'/extension/web/pair', '/extension/web/preview', '/extension/web/save'}
MAX_REQUEST_BYTES = 256000


def cors_headers(origin):
    return {'Access-Control-Allow-Origin': origin, 'Vary': 'Origin',
            'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Authorization, Content-Type',
            'Access-Control-Max-Age': '0', 'Cache-Control': 'no-store'}


def extension_boundary(bridge, request):
    path, origin = request.url.path, request.headers.get('origin', '')
    if path not in EXTENSION_PATHS:
        return JSONResponse({'detail': 'Browser route not found.'}, status_code=404)
    if not bridge.allowed_origin(origin, pairing=path.endswith('/pair')):
        return JSONResponse({'detail': 'This extension origin is not approved.'}, status_code=403)
    headers = cors_headers(origin)
    if request.method == 'OPTIONS':
        requested = {part.strip().lower() for part in request.headers.get('access-control-request-headers', '').split(',') if part.strip()}
        if request.headers.get('access-control-request-method') != 'POST' or not requested <= {'authorization', 'content-type'}:
            return JSONResponse({'detail': 'Browser preflight rejected.'}, status_code=403)
        if request.headers.get('access-control-request-private-network') == 'true':
            headers['Access-Control-Allow-Private-Network'] = 'true'
        return Response(status_code=204, headers=headers)
    if request.method != 'POST':
        return JSONResponse({'detail': 'Only POST is allowed.'}, status_code=405, headers=headers)
    if not path.endswith('/pair'):
        owner = bridge.authorize(origin, request.headers.get('authorization', ''))
        if not owner:
            return JSONResponse({'detail': 'Browser access is invalid or revoked. Pair again in Bej.'}, status_code=401, headers=headers)
        request.state.web_owner = owner
    return None


class Fields(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Capture(Fields):
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=4000)
    text: str = Field(min_length=1, max_length=50000)
    mode: Literal['selection', 'page', 'paste']


class Pairing(Fields):
    extensionId: str = Field(pattern=r'^[a-p]{32}$')


class Code(Fields):
    pairingCode: str = Field(min_length=1, max_length=128)


class Preview(Fields):
    previewId: str = Field(pattern=r'^[a-f0-9]{32}$')


class CaptureID(Fields):
    captureId: str = Field(pattern=r'^[a-f0-9]{32}$')


async def payload(request, model):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_REQUEST_BYTES:
            raise HTTPException(413, 'Capture request is too large.')
        data.extend(chunk)
    try:
        return model.model_validate_json(bytes(data))
    except ValidationError:
        # Never echo request data, including a pairing code or page contents.
        raise HTTPException(422, 'Invalid web capture input. Check the fields and their limits.') from None


def public(value):
    result = dict(value)
    for field in ('expiresAt', 'pairingExpiresAt'):
        if field in result:
            result[field] = datetime.fromtimestamp(result[field], timezone.utc).isoformat()
    return result


def install_web_routes(app, notes, bridge):
    router = APIRouter()

    @router.get('/api/web/status')
    def status():
        return {**public(bridge.status()), 'destination': DESTINATION}

    @router.post('/api/web/pairing')
    async def begin(request: Request):
        body = await payload(request, Pairing)
        return public(bridge.begin(body.extensionId))

    @router.post('/api/web/revoke')
    async def revoke(request: Request):
        await payload(request, Fields)
        bridge.revoke()
        return {'revoked': True}

    @router.post('/extension/web/pair')
    async def pair(request: Request):
        body = await payload(request, Code)
        return bridge.pair(request.headers.get('origin'), body.pairingCode)

    @router.post('/api/web/preview')
    @router.post('/extension/web/preview')
    async def preview(request: Request):
        body = await payload(request, Capture)
        owner = request.state.web_owner if request.url.path.startswith('/extension/') else 'workspace'
        return public(notes.preview(body.model_dump(), owner))

    @router.post('/api/web/save')
    @router.post('/extension/web/save')
    async def save(request: Request):
        body = await payload(request, Preview)
        owner = request.state.web_owner if request.url.path.startswith('/extension/') else 'workspace'
        return notes.save(body.previewId, owner)

    @router.get('/api/web/captures')
    def captures():
        return {'captures': notes.list_captures()}

    @router.post('/api/web/delete-preview')
    async def delete_preview(request: Request):
        body = await payload(request, CaptureID)
        return notes.delete_preview(body.captureId, 'workspace')

    @router.post('/api/web/delete')
    async def delete(request: Request):
        body = await payload(request, Preview)
        return notes.delete(body.previewId, 'workspace')

    app.include_router(router)
