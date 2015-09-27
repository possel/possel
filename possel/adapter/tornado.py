#!/usr/bin/env python3
# -*- coding: utf8 -*-
import logbook
from tornado import gen, ioloop, tcpclient

CHANNEL_JOIN_DELAY = 15

logger = logbook.Logger(__name__)
loopinstance = ioloop.IOLoop.instance()


class LineStream:
    def __init__(self):
        self.tcp_client_factory = tcpclient.TCPClient()
        self.line_callback = None
        self.connect_callback = None

    @gen.coroutine
    def connect(self, host, port):
        logger.debug('Connecting to server {}:{}', host, port)
        self.connection = yield self.tcp_client_factory.connect(host, port)
        logger.debug('Connected.')
        if self.connect_callback is not None:
            self.connect_callback()
            logger.debug('Called post-connection callback')
        self._schedule_line()

    def handle_line(self, line):
        if self.line_callback is not None:
            self.line_callback(line)

        self._schedule_line()

    def _schedule_line(self):
        self.connection.read_until(b'\n', self.handle_line)

    def write_function(self, line):
        if line[-1] != '\n':
            line += '\n'
        return self.connection.write(line.encode('utf8'))


def connect(args, server_handler):
    import possel

    line_stream = LineStream()

    # Attach instances
    server_handler.write_function = line_stream.write_function
    line_stream.connect_callback = server_handler.pre_line
    line_stream.line_callback = server_handler.handle_line

    if args.die_on_exception:
        loopinstance.handle_callback_exception = possel._exc_exit

    # Connect to server
    line_stream.connect(args.server, 6667)

    # Join channels
    for channel in args.channel:
        loopinstance.call_later(CHANNEL_JOIN_DELAY, server_handler.channels[channel].join)


def main_loop():
    loopinstance.start()
