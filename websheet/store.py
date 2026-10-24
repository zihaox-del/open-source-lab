import fcntl
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .core import ExtractionError, extract, fetch, origin, source_id, validate_columns

class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, fields TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL DEFAULT 'static');
            CREATE TABLE IF NOT EXISTS rows(job_id TEXT NOT NULL, position INTEGER NOT NULL, source_id TEXT NOT NULL,
            source_url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', data TEXT NOT NULL DEFAULT '{}', error TEXT,
            PRIMARY KEY(job_id, source_id));''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def create(self, urls, fields, reviewed, engine="static"):
        if not reviewed:
            raise ExtractionError('请先预览并确认提取规则')
        validate_columns(fields)
        if not 1 <= len(urls) <= 100:
            raise ExtractionError('每个任务需要 1–100 个 URL')
        if len({origin(url) for url in urls}) != 1:
            raise ExtractionError('一个任务只允许同源 URL')
        if engine not in ("static", "browser-demo"):
            raise ExtractionError("未知引擎")
        if engine == "browser-demo" and origin(urls[0]) != "demo://catalog":
            raise ExtractionError("浏览器演示仅支持内置 demo://catalog 页面")
        urls = list(dict.fromkeys(urls))
        job_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?)', (job_id, json.dumps([f.model_dump() for f in fields]), 'ready', engine))
            db.executemany('INSERT INTO rows(job_id,position,source_id,source_url) VALUES(?,?,?,?)',
                           [(job_id, n, source_id(url), url) for n, url in enumerate(urls)])
        return self.get(job_id)

    def get(self, job_id):
        with self.connect() as db:
            job = db.execute('SELECT fields,status,engine FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise KeyError(job_id)
            rows = db.execute('SELECT source_id,source_url,status,data,error FROM rows WHERE job_id=? ORDER BY position', (job_id,)).fetchall()
        result = [{'source_id': r[0], 'source_url': r[1], 'status': r[2], 'data': json.loads(r[3]), 'error': r[4]} for r in rows]
        return dict(id=job_id, engine=job[2], fields=json.loads(job[0]), status=job[1], total=len(rows),
                    completed=sum(r['status'] == 'success' for r in result), failed=sum(r['status'] == 'failed' for r in result), rows=result)

    def run(self, job_id, fetcher=fetch):
        from .core import Column
        # OS lock is released on process death; each completed row is separately committed.
        with self.path.with_suffix('.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ExtractionError('已有任务运行中，请稍后查看状态') from exc
            job = self.get(job_id)
            fields = [Column(**f) for f in job['fields']]
            with self.connect() as db:
                db.execute('UPDATE jobs SET status=? WHERE id=?', ('running', job_id))
            for row in job['rows']:
                if row['status'] != 'pending':
                    continue
                try:
                    data, status, error = extract(fetcher(row['source_url']), fields), 'success', None
                except Exception as exc:
                    data, status = {}, 'failed'
                    error = str(exc) if isinstance(exc, ExtractionError) else '提取失败；请检查页面和规则'
                with self.connect() as db:
                    db.execute('UPDATE rows SET status=?,data=?,error=? WHERE job_id=? AND source_id=?',
                               (status, json.dumps(data, ensure_ascii=False), error, job_id, row['source_id']))
            with self.connect() as db:
                db.execute('UPDATE jobs SET status=? WHERE id=?', ('complete', job_id))
            return self.get(job_id)
