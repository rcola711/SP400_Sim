"""Virtual serial port via a pseudo-terminal (Linux/macOS only).

Host software opens the printed /dev/pts/N path as if it were the real
instrument's serial port.
"""

from __future__ import annotations

import os
import select
import tty

from ..protocol import CommandProcessor


def run_pty(processor: CommandProcessor, link: str | None = None) -> None:
    master, slave = os.openpty()
    tty.setraw(slave)
    path = os.ttyname(slave)
    if link:
        if os.path.islink(link):
            os.unlink(link)
        os.symlink(path, link)
        print(f"SP400 simulator on {path} (symlink {link})", flush=True)
    else:
        print(f"SP400 simulator on {path}", flush=True)

    term = processor.device.profile.line_terminator.encode()
    buf = b""
    try:
        while True:
            ready, _, _ = select.select([master], [], [], 0.5)
            if not ready:
                continue
            buf += os.read(master, 1024)
            while True:
                idx = min((i for i in (buf.find(b"\n"), buf.find(b"\r")) if i >= 0), default=-1)
                if idx < 0:
                    break
                line, buf = buf[:idx], buf[idx + 1 :]
                reply = processor.handle(line.decode(errors="replace"))
                if reply is not None:
                    os.write(master, reply.encode() + term)
    except KeyboardInterrupt:
        pass
    finally:
        if link and os.path.islink(link):
            os.unlink(link)
        os.close(master)
        os.close(slave)
