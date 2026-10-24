from pathlib import Path
from contextlib import nullcontext
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from . import __version__
from .core import Column, ExtractionError, export_rows, extract, fetch, candidate_report, link_report
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
        return {'status': 'ok', 'app': 'websheet-agent', 'version': __version__}

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
        return candidate_report(fetch(body.url))

    @app.post('/api/discover')
    def discover(body: Sample):
        return link_report(fetch(body.url), body.url)

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

    @app.post('/api/review')
    def review(body: Review):
        config = store.configuration(body.urls, body.fields, body.engine, body.parent_job_id)
        with store.connect() as db:
            store._validate_parent(db, config)
        urls = config['urls']
        selected = [urls[i] for i in sorted({0, len(urls) // 2, len(urls) - 1})]
        samples = []
        if body.engine == 'browser-demo':
            from .browser import renderer
            scope = renderer()
        else:
            scope = nullcontext(fetch)
        try:
            with scope as read:
                for url in selected:
                    try:
                        samples.append(dict(source_url=url, row=extract(read(url), body.fields), error=None))
                    except Exception as exc:
                        samples.append(dict(source_url=url, row=None, error=str(exc) if isinstance(exc, ExtractionError) else '读取失败；请检查页面和规则'))
        except Exception as exc:
            # Renderer startup failures remain visible failures for every selected source.
            message = str(exc) if isinstance(exc, ExtractionError) else '无法启动演示渲染器；请检查运行环境'
            samples = [dict(source_url=url, row=None, error=message) for url in selected]
        all_ok = all(item['error'] is None for item in samples)
        positional = any(' > ' in f.selector or ':nth-of-type' in f.selector for f in body.fields)
        return dict(samples=samples, all_ok=all_ok, positional_warning=positional,
                    review_token=store.issue_review(config) if all_ok else None)

    @app.post('/api/suggest')
    def ai_suggest(body: Suggestion):
        if not body.allow_ai_upload:
            raise ExtractionError('需要明确同意向 DeepSeek 发送样例页面摘要')
        fields = suggest(fetch(body.url), body.names)
        return {'fields': [f.model_dump() for f in fields], 'provider': 'deepseek'}

    @app.post('/api/jobs')
    def create(body: NewJob):
        return store.create(body.urls, body.fields, body.reviewed, body.engine, body.request_id,
                            body.parent_job_id, body.review_token, require_review=True)

    @app.get('/api/jobs/{job_id}/retry-draft')
    def retry_draft(job_id: str):
        return store.retry_draft(job_id)

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

class Review(BaseModel):
    engine: Literal["static", "browser-demo"] = "static"
    urls: list[str] = Field(min_length=1, max_length=100)
    fields: list[Column] = Field(min_length=1, max_length=20)
    parent_job_id: str | None = Field(default=None, min_length=1, max_length=80)

class NewJob(Review):
    review_token: str | None = Field(default=None, min_length=1, max_length=80)
    request_id: str | None = Field(default=None, min_length=1, max_length=80)
    reviewed: bool = False

class Suggestion(BaseModel):
    url: str = Field(max_length=2048)
    names: list[str] = Field(min_length=1, max_length=20)
    allow_ai_upload: bool = False
