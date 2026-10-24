"""Nonblocking process lock; closing the handle releases it, including on exit."""
import errno
import os


def try_lock(path):
    handle = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            # Windows explicitly permits byte-range locks beyond EOF.
            # Keep this file empty: writing a lock byte races other holders.
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return None
        raise
    return handle
