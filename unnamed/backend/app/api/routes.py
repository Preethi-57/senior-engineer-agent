from fastapi import APIRouter, Depends, HTTPException, Request
from ..core.auth import require_api_key
from ..core.rate_limit import rate_limit
from ..models.domain import RunCreate
from ..services.run_manager import manager

router=APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key),Depends(rate_limit)])

@router.post('/runs')
def create(req:RunCreate):
    if not req.repo_url.startswith('https://github.com/'):
        raise HTTPException(400,'Only GitHub HTTPS repositories are supported for the production workflow.')
    return manager.create(req)

@router.post('/runs/{rid}/analyze')
async def analyze(rid:str):
    try:
        queued=manager.enqueue(rid,'analyze')
        if queued: return {'run_id':rid,'status':'queued','queue':'redis'}
        return await manager.analyze(rid)
    except KeyError:raise HTTPException(404,'Run not found')
    except ValueError as e:raise HTTPException(400,str(e))

@router.get('/runs/{rid}')
def get(rid:str):
    try:return manager.get(rid)
    except KeyError:raise HTTPException(404,'Run not found')

@router.post('/runs/{rid}/approve')
def approve(rid:str,body:dict):
    try:return manager.approve(rid,body.get('finding_ids',[]))
    except KeyError:raise HTTPException(404,'Run not found')
    except ValueError as e:raise HTTPException(400,str(e))

@router.post('/runs/{rid}/execute')
async def execute(rid:str):
    try:
        queued=manager.enqueue(rid,'execute')
        if queued: return {'run_id':rid,'status':'queued','queue':'redis'}
        return await manager.execute_async(rid)
    except KeyError:raise HTTPException(404,'Run not found')
    except ValueError as e:raise HTTPException(400,str(e))

@router.get('/runs/{rid}/report')
def report(rid:str):
    try:return manager.report(rid)
    except KeyError:raise HTTPException(404,'Run not found')

@router.get('/health')
def health():return {'status':'ok','service':'ai-sre-agent'}

@router.get('/ready')
def ready():
    from ..core.settings import settings
    return {'status':'ready','database':str(settings.database),'llm_configured':bool(settings.llm_api_key),'github_push_enabled':settings.allow_github_push,'pr_creation_enabled':settings.allow_pr_creation}
