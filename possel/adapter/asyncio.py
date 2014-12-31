#!/usr/bin/env python3
# -*- coding: utf8 -*-
import asyncio
import functools

import logbook

CHANNEL_JOIN_DELAY = 15

logger = logbook.Logger(__name__)
loop = asyncio.get_event_loop()


def _connect_done(args, server_handler, log_handler, t):
    reader, writer = t.result()
    logger.debug('Connected.')

    with log_handler.applicationbound():
        server_handler.write_function = functools.partial(_write, writer)
        loop.call_soon(server_handler.pre_line())
        for channel in args.channel:
            loop.call_later(CHANNEL_JOIN_DELAY, server_handler.channels[channel].join)

        asyncio.async(_read(reader, server_handler), loop=loop)


def _write(writer, line):
    if line[-1] != '\n':
        line += '\n'
    writer.write(line.encode('utf8'))


@asyncio.coroutine
def _read(reader, server_handler):
    line = yield from reader.readline()
    loop.call_soon(server_handler.handle_line, line)
    asyncio.async(_read(reader, server_handler), loop=loop)


def connect(args, server_handler, log_handler):
    logger.debug('Connecting to server {}:{}', args.server, 6667)
    t = asyncio.async(asyncio.open_connection(args.server, 6667), loop=loop)
    t.add_done_callback(functools.partial(_connect_done, args, server_handler, log_handler))
    loop.run_forever()
