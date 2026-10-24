from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from .core import Column, ExtractionError, export_rows, extract, fetch, candidates, discover_links
from .store import Store
from .paths import default_db_path
from .ai import suggest


def create_app(db_path=None):
    app = FastAPI(title='WebSheet Agent', docs_url=None, redoc_url=None)
    store = Store(db_path or default_db_path())
    app.state.store = store

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.url.hostname
        allowed = {'127.0.0.1', 'localhost', '[::1]', '::1'}
        origin_header = request.headers.get('origin')
        # Host validation prevents DNS rebinding; cross-origin writes cannot drive the local service.
        if host not in allowed or (origin_header and origin_header != str(request.base_url).rstrip('/')):
            return JSONResponse({'detail': '仅允许本机同源访问'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': '拒绝跨站请求'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; connect-src 'self'"
        return response

    @app.exception_handler(ExtractionError)
    async def extraction_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({'detail': '任务不存在'}, status_code=404)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'app': 'websheet-agent'}

    @app.get('/')
    def index():
        return FileResponse(Path(__file__).parent / 'static/index.html')

    @app.get('/api/demo')
    def demo():
        return {'urls': [f'demo://catalog/{n}' for n in range(1, 31)], 'sample_url': 'demo://catalog/1',
                'fields': [{'name': '名称', 'selector': 'h1', 'attribute': 'text'},
                           {'name': '价格', 'selector': '.price', 'attribute': 'text'},
                           {'name': '编号', 'selector': '#sku', 'attribute': 'text'}]}

    @app.post('/api/inspect')
    def inspect(body: Sample):
        return {'candidates': candidates(fetch(body.url))}

    @app.post('/api/discover')
    def discover(body: Sample):
        return {'links': discover_links(fetch(body.url), body.url)}

    @app.get('/api/jobs')
    def history():
        return {'jobs': store.list_jobs()}

    @app.post('/api/preview')
    def preview(body: Preview):
        if body.engine == 'browser-demo':
            from .browser import renderer
            from .core import origin
            if origin(body.url) != 'demo://catalog':
                raise ExtractionError('浏览器演示仅支持内置页面')
            with renderer() as render:
                return {'source_url': body.url, 'row': extract(render(body.url), body.fields)}
        return {'source_url': body.url, 'row': extract(fetch(body.url), body.fields)}

    @app.post('/api/suggest')
    def ai_suggest(body: Suggestion):
        if not body.allow_ai_upload:
            raise ExtractionError('需要明确同意向 DeepSeek 发送样例页面摘要')
        fields = suggest(fetch(body.url), body.names)
        return {'fields': [f.model_dump() for f in fields], 'provider': 'deepseek'}

    @app.post('/api/jobs')
    def create(body: NewJob):
        return store.create(body.urls, body.fields, body.reviewed, body.engine, body.request_id)

    @app.get('/api/jobs/{job_id}')
    def get(job_id: str):
        return store.get(job_id)

    @app.post('/api/jobs/{job_id}/run')
    def run(job_id: str):
        return store.start(job_id)

    @app.post('/api/jobs/{job_id}/pause')
    def pause(job_id: str):
        return store.pause(job_id)

    @app.get('/api/jobs/{job_id}/export')
    def export(job_id: str, format: str = 'csv'):
        data = export_rows(store.get(job_id), format)
        return Response(data, media_type='text/csv' if format == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': f'attachment; filename="websheet-{job_id}.{format}"'})
    return app

class Sample(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

class Preview(BaseModel):
    engine: Literal["static", "browser-demo"] = "static"
    url: str = Field(max_length=2048)
    fields: list[Column] = Field(min_length=1, max_length=20)

class NewJob(BaseModel):
    request_id: str | None = Field(default=None, min_length=1, max_length=80)
    engine: Literal["static", "browser-demo"] = "static"
    urls: list[str] = Field(min_length=1, max_length=100)
    fields: list[Column] = Field(min_length=1, max_length=20)
    reviewed: bool = False

class Suggestion(BaseModel):
    url: str = Field(max_length=2048)
    names: list[str] = Field(min_length=1, max_length=20)
    allow_ai_upload: bool = False
