#!/usr/bin/env python3
# -*- coding: utf8 -*-
import asyncio
import functools

import logbook

CHANNEL_JOIN_DELAY = 15

logger = logbook.Logger(__name__)
loop = asyncio.get_event_loop()


def connect_done(args, server_handler, tcp_open_future):
    reader, writer = tcp_open_future.result()
    logger.debug('Connected.')

    server_handler.write_function = functools.partial(write, writer)
    loop.call_soon(server_handler.pre_line())
    for channel in args.channel:
        loop.call_later(CHANNEL_JOIN_DELAY, server_handler.channels[channel].join)

    asyncio.async(read(reader, server_handler), loop=loop)


def write(writer, line):
    if line[-1] != '\n':
        line += '\n'
    writer.write(line.encode('utf8'))


@asyncio.coroutine
def read(reader, server_handler):
    line = yield from reader.readline()
    loop.call_soon(server_handler.handle_line, line)
    asyncio.async(read(reader, server_handler), loop=loop)


def connect(args, server_handler):
    logger.debug('Connecting to server {}:{}', args.server, 6667)
    tcp_open_future = asyncio.async(asyncio.open_connection(args.server, 6667), loop=loop)
    tcp_open_future.add_done_callback(functools.partial(connect_done, args, server_handler))


def main_loop():
    loop.run_forever()


__all__ = ['connect', 'main_loop']
