import asyncio
import os
import sys
import threading
import time

import pytest

from sp400_sim import CommandProcessor, Device, load_profile
from sp400_sim.transports.tcp import serve_tcp


def make_proc():
    return CommandProcessor(Device(load_profile(), seed=0))


def test_tcp_roundtrip():
    async def run():
        server = await serve_tcp(make_proc(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(b"*IDN?\nSTAT?\n")
            await w.drain()
            idn = (await r.readline()).decode().strip()
            stat = (await r.readline()).decode().strip()
            w.close()
            return idn, stat

    idn, stat = asyncio.run(run())
    assert idn.split(",")[1] == "SP400"
    assert stat == "IDLE"


@pytest.mark.skipif(sys.platform == "win32", reason="pty not available on Windows")
def test_pty_roundtrip(capsys, monkeypatch):
    import sp400_sim.transports.pty_serial as ps

    opened = {}
    real_openpty = os.openpty

    def spy_openpty():
        m, s = real_openpty()
        opened["path"] = os.ttyname(s)
        return m, s

    monkeypatch.setattr(ps.os, "openpty", spy_openpty)
    t = threading.Thread(target=ps.run_pty, args=(make_proc(),), daemon=True)
    t.start()
    for _ in range(50):
        if "path" in opened:
            break
        time.sleep(0.02)

    fd = os.open(opened["path"], os.O_RDWR | os.O_NOCTTY)
    try:
        os.write(fd, b"STAT?\r")
        data = b""
        deadline = time.time() + 2
        while b"\n" not in data and time.time() < deadline:
            data += os.read(fd, 100)
        assert data.strip() == b"IDLE"
    finally:
        os.close(fd)
