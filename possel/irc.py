#!/usr/bin/env python3
# -*- coding: utf8 -*-
from tornado import ioloop, gen, tcpclient

loopinstance = ioloop.IOLoop.instance()


def split_irc_line(s):
    """Breaks a message from an IRC server into its prefix, command, and arguments.
    """
    prefix = ''
    trailing = []
    if not s:
        # Raise an exception of some kind
        pass
    if s[0] == ':':
        prefix, s = s[1:].split(' ', 1)
    if s.find(' :') != -1:
        s, trailing = s.split(' :', 1)
        args = s.split()
        args.append(trailing)
    else:
        args = s.split()
    command = args.pop(0)
    return prefix, command, args


class LineStream:
    def __init__(self):
        self.tcp_client_factory = tcpclient.TCPClient()
        self.line_callback = None
        self.connect_callback = None

    @gen.coroutine
    def connect(self, host, port):
        print('connecting')
        self.connection = yield self.tcp_client_factory.connect(host, port)
        print('connected')
        if self.connect_callback is not None:
            self.connect_callback()
        print('callbacked')
        self._schedule_line()

    def handle_line(self, line):
        if self.line_callback is not None:
            self.line_callback(line, self._write)

        self._schedule_line()

    def _schedule_line(self):
        self.connection.read_until(b'\n', self.handle_line)

    def _write(self, line):
        if line[-1] != '\n':
            line += '\n'
        return self.connection.write(line.encode('utf8'))


class IRCClient:
    def __init__(self, write_function):
        self._write = write_function

    def pong(self, value):
        self._write('PONG :{}'.format(value))

    def pre_line(self):
        self._write('NICK butts')
        self._write('USER mother 0 * :Your Mother')

    def handle_line(self, line, write_func):
        line = str(line, encoding='utf8').strip()
        (prefix, command, args) = split_irc_line(line)

        try:
            handler = getattr(self, 'on_{}'.format(command.lower()))
        except AttributeError:
            self.log_unknown(command, prefix, args)
        else:
            handler(prefix, *args)

    def log_unknown(self, command, prefix, args):
        print('Unknown Command received: {} with args ({}) from prefix {}'.format(command, args, prefix))

    # ===============
    # Handlers follow
    # ===============
    def on_ping(self, prefix, token, *args):
        self._write('PONG :{}'.format(token))

    def on_notice(self, prefix, _, message):
        print('NOTICE: {}'.format(message))

    def on_join(self, who, channel):
        pass

    def on_372(self, *args):
        pass

    def on_353(self, prefix, who, _, channel, names):
        pass

    def on_366(self, prefix, who, channel, *args):
        pass
    # =============
    # Handlers done
    # =============

    def join_channel(self, channel, password=None):
        if password:
            self._write('JOIN {} {}'.format(channel, password))
        else:
            self._write('JOIN {}'.format(channel))


class IRCChannel:
    def __init__(self, write_function, name):
        self._write = write_function
        self.name = name
        self.nicks = []
        self.messages = []


def main():
    line_stream = LineStream()
    client = IRCClient(line_stream._write)

    line_stream.connect_callback = client.pre_line
    line_stream.line_callback = client.handle_line

    line_stream.connect('irc.imaginarynet.org.uk', 6667)

    loopinstance.call_later(2, client.join_channel, '#compsoc-minecraft')

    loopinstance.start()

if __name__ == '__main__':
    import sys
    main(*sys.argv[1:])
