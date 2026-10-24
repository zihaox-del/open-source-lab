import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path

from .locking import try_lock
from .core import ExtractionError, extract, fetch, origin, source_id, validate_columns


_claim_guard = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, fields TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL DEFAULT 'static');
            CREATE TABLE IF NOT EXISTS rows(job_id TEXT NOT NULL, position INTEGER NOT NULL, source_id TEXT NOT NULL,
            source_url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', data TEXT NOT NULL DEFAULT '{}', error TEXT,
            PRIMARY KEY(job_id, source_id));''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(jobs)')}
            for name in ('created_at', 'updated_at', 'error', 'request_id', 'request_payload'):
                if name not in columns:
                    db.execute(f'ALTER TABLE jobs ADD COLUMN {name} TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS jobs_request_id ON jobs(request_id)')
            db.execute('UPDATE jobs SET created_at=COALESCE(created_at,?), updated_at=COALESCE(updated_at,?)', (_now(), _now()))
        self._workers = []
        self._stopping = threading.Event()
        self._recover()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _lock(self):
        return try_lock(self.path.with_suffix('.lock'))

    def _recover(self):
        # Only the process holding the OS lock can declare a worker interrupted.
        # A second Store instance must never reset a live worker's status.
        lock = self._lock()
        if lock is not None:
            with lock, self.connect() as db:
                db.execute("UPDATE jobs SET status=CASE WHEN status='pausing' THEN 'paused' ELSE 'interrupted' END, updated_at=? WHERE status IN ('running','pausing')", (_now(),))

    def create(self, urls, fields, reviewed, engine='static', request_id=None):
        if not reviewed:
            raise ExtractionError('请先预览并确认提取规则')
        validate_columns(fields)
        if not 1 <= len(urls) <= 100:
            raise ExtractionError('每个任务需要 1–100 个 URL')
        if len({origin(url) for url in urls}) != 1:
            raise ExtractionError('一个任务只允许同源 URL')
        if engine not in ('static', 'browser-demo'):
            raise ExtractionError('未知引擎')
        if engine == 'browser-demo' and origin(urls[0]) != 'demo://catalog':
            raise ExtractionError('浏览器演示仅支持内置 demo://catalog 页面')
        if request_id is not None and (not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128):
            raise ExtractionError('请求标识必须为 1–128 个字符')
        field_data = [f.model_dump() for f in fields]
        payload = json.dumps(dict(urls=urls, fields=field_data, reviewed=reviewed, engine=engine), sort_keys=True, ensure_ascii=False)
        unique_urls = list(dict.fromkeys(urls))
        job_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT id,request_payload FROM jobs WHERE request_id=?', (request_id,)).fetchone() if request_id is not None else None
            if previous:
                if previous[1] != payload:
                    raise ExtractionError('该请求标识已用于其他内容，请重新预览后创建任务')
                job_id = previous[0]
            else:
                timestamp = _now()
                db.execute('INSERT INTO jobs(id,fields,status,engine,created_at,updated_at,request_id,request_payload) VALUES(?,?,?,?,?,?,?,?)',
                           (job_id, json.dumps(field_data), 'ready', engine, timestamp, timestamp, request_id, payload))
                db.executemany('INSERT INTO rows(job_id,position,source_id,source_url) VALUES(?,?,?,?)',
                               [(job_id, n, source_id(url), url) for n, url in enumerate(unique_urls)])
        return self.get(job_id)

    def get(self, job_id):
        self._recover()
        with self.connect() as db:
            db.execute('BEGIN')  # Keep status, counts and rows in one read snapshot.
            job = db.execute('SELECT fields,status,engine,created_at,updated_at,error FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise KeyError(job_id)
            rows = db.execute('SELECT source_id,source_url,status,data,error FROM rows WHERE job_id=? ORDER BY position', (job_id,)).fetchall()
        result = [{'source_id': r[0], 'source_url': r[1], 'status': r[2], 'data': json.loads(r[3]), 'error': r[4]} for r in rows]
        return dict(id=job_id, engine=job[2], fields=json.loads(job[0]), status=job[1], total=len(rows),
                    completed=sum(r['status'] == 'success' for r in result), failed=sum(r['status'] == 'failed' for r in result), rows=result,
                    created_at=job[3], updated_at=job[4], error=job[5])

    def list_jobs(self):
        self._recover()
        with self.connect() as db:
            ids = [row[0] for row in db.execute('SELECT id FROM jobs ORDER BY created_at DESC,rowid DESC')]
        return [self.get(job_id) for job_id in ids]

    def pause(self, job_id):
        self.get(job_id)
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=CASE WHEN status='running' THEN 'pausing' ELSE 'paused' END,updated_at=? WHERE id=? AND status IN ('ready','running','interrupted')", (_now(), job_id))
        return self.get(job_id)

    def _claim(self, job_id):
        # Serialize the tiny claim/status transition across Store instances.
        with _claim_guard:
            if self._stopping.is_set():
                raise ExtractionError('服务正在停止，请重启后继续任务')
            return self._claim_locked(job_id)

    def _claim_locked(self, job_id):
        self.get(job_id)  # Validate the ID even when another job holds the lock.
        lock = self._lock()
        if lock is None:
            job = self.get(job_id)
            if job['status'] in ('running', 'pausing', 'complete'):
                return None
            raise ExtractionError('已有任务运行中，请稍后查看状态')
        try:
            job = self.get(job_id)
            if job['status'] == 'complete':
                lock.close()
                return None
            with self.connect() as db:
                db.execute('UPDATE jobs SET status=?,error=NULL,updated_at=? WHERE id=?', ('running', _now(), job_id))
            return lock
        except BaseException:
            lock.close()
            raise

    def start(self, job_id, fetcher=None):
        lock = self._claim(job_id)
        if lock is not None:
            worker = threading.Thread(target=self._background, args=(job_id, lock, fetcher), daemon=True, name=f'websheet-{job_id}')
            try:
                self._workers.append(worker)
                worker.start()
            except BaseException:
                self._set_interrupted(job_id, '任务未能启动，请重试')
                lock.close()
                raise
        return self.get(job_id)

    def _set_interrupted(self, job_id, error):
        with self.connect() as db:
            db.execute('UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?', ('interrupted', error, _now(), job_id))

    def _background(self, job_id, lock, fetcher):
        try:
            self._execute(job_id, lock, fetcher)
        except BaseException:
            # _execute persists a safe, actionable error before releasing the lock.
            pass

    def run(self, job_id, fetcher=None):
        lock = self._claim(job_id)
        if lock is None:
            return self.get(job_id)
        return self._execute(job_id, lock, fetcher)

    def _execute(self, job_id, lock, fetcher):
        from .core import Column
        with lock:
            try:
                job = self.get(job_id)
                fields = [Column(**f) for f in job['fields']]
                if fetcher is not None:
                    scope = nullcontext(fetcher)
                elif job['engine'] == 'browser-demo':
                    from .browser import renderer
                    scope = renderer()
                else:
                    scope = nullcontext(fetch)
                # Browser objects are created, used and closed on this worker thread.
                with scope as read_page:
                    for row in job['rows']:
                        if row['status'] != 'pending':
                            continue
                        with self.connect() as db:
                            status = db.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()[0]
                            if status == 'pausing' or self._stopping.is_set():
                                db.execute('UPDATE jobs SET status=?,updated_at=? WHERE id=?', ('paused', _now(), job_id))
                                break
                        try:
                            data, status, error = extract(read_page(row['source_url']), fields), 'success', None
                        except Exception as exc:
                            data, status = {}, 'failed'
                            error = str(exc) if isinstance(exc, ExtractionError) else '提取失败；请检查页面和规则'
                        with self.connect() as db:
                            db.execute('UPDATE rows SET status=?,data=?,error=? WHERE job_id=? AND source_id=?',
                                       (status, json.dumps(data, ensure_ascii=False), error, job_id, row['source_id']))
                            db.execute('UPDATE jobs SET updated_at=? WHERE id=?', (_now(), job_id))
                with self.connect() as db:
                    remaining = db.execute("SELECT COUNT(*) FROM rows WHERE job_id=? AND status='pending'", (job_id,)).fetchone()[0]
                    db.execute('UPDATE jobs SET status=?,updated_at=? WHERE id=?', ('paused' if remaining else 'complete', _now(), job_id))
            except BaseException as exc:
                message = str(exc) if isinstance(exc, ExtractionError) else '任务已中断；已完成的结果已保存，可继续执行'
                self._set_interrupted(job_id, message)
                raise
            return self.get(job_id)

    def shutdown(self):
        """Finish the current row, preserve pending rows, then release all locks."""
        with _claim_guard:
            self._stopping.set()
        for worker in self._workers:
            if worker.ident is not None:
                worker.join()
