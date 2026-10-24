"""Local readiness checks. Never installs packages or changes system settings."""
import importlib.util
import socket
import sys
import tempfile
from .paths import default_db_path


def check(port=8765):
    errors = []
    if sys.version_info < (3, 11):
        errors.append('需要 Python 3.11 或更新版本。')
    for module in ('fastapi', 'uvicorn', 'pydantic', 'httpx', 'lxml', 'openpyxl'):
        if importlib.util.find_spec(module) is None:
            errors.append(f'缺少依赖 {module}，请在虚拟环境运行 python -m pip install -r requirements.txt。')
    directory = default_db_path().parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=directory):
            pass
    except OSError:
        errors.append('数据目录不可写，请选择可写的 WEBSHEET_DB 路径。')
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    except OSError:
        errors.append(f'无法监听本机端口 {port}：可能已有服务运行，或环境限制了网络套接字。请关闭占用端口的程序后重试，不会打开或接管现有服务。')
    return errors


def main():
    errors = check()
    for line in errors:
        print('检查未通过：' + line)
    if not errors:
        print('基础检查通过。仅在本机运行；不检查公网兼容性，也不验证可选浏览器引擎。')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
