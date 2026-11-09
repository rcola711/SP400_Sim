"""TCP server transport (one shared device, many clients)."""

from __future__ import annotations

import asyncio
import logging

from ..protocol import CommandProcessor

log = logging.getLogger(__name__)


async def serve_tcp(processor: CommandProcessor, host: str, port: int) -> asyncio.Server:
    term = processor.device.profile.line_terminator.encode()
    lock = asyncio.Lock()

    async def on_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        log.info("client connected: %s", peer)
        try:
            while line := await reader.readline():
                async with lock:
                    reply = processor.handle(line.decode(errors="replace"))
                log.debug("%s <- %r -> %r", peer, line, reply)
                if reply is not None:
                    writer.write(reply.encode() + term)
                    await writer.drain()
        except ConnectionError:
            pass
        finally:
            log.info("client disconnected: %s", peer)
            writer.close()

    return await asyncio.start_server(on_client, host, port)


def run_tcp(processor: CommandProcessor, host: str, port: int) -> None:
    async def main() -> None:
        server = await serve_tcp(processor, host, port)
        addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
        print(f"SP400 simulator listening on {addrs}", flush=True)
        async with server:
            await server.serve_forever()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
