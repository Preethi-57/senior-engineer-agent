from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router
from .core.settings import settings
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app=FastAPI(title='AI-SRE Agent',version='2.0.0',description='Production-oriented agentic software reliability engineering platform',docs_url='/docs' if settings.app_env!='production' else None,redoc_url=None)
origins=[x.strip() for x in __import__('os').getenv('CORS_ORIGINS','http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type','X-API-Key'])
app.include_router(router)
@app.get('/')
def root():return {'name':'AI-SRE Agent','version':'2.0.0','health':'/api/v1/health','ready':'/api/v1/ready'}

@app.get("/metrics")
def metrics():
    if not settings.metrics_enabled: return Response(status_code=404)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
