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


class IRCClient:
    def __init__(self):
        self.tcp_client_factory = tcpclient.TCPClient()

    def start(self):
        loopinstance.add_callback(self.connect)

    def _write(self, line):
        if line[-1] != '\n':
            line += '\n'
        return self.connection.write(line.encode('utf8'))

    def pong(self, value):
        self._write('PONG :{}'.format(value))

    def handle_line(self, line):
        line = str(line, encoding='utf8').strip()
        (prefix, command, args) = split_irc_line(line)
        print('Prefix: {}\nCommand: {}\nArgs: {}\n\n'.format(prefix, command, args))

        if command.lower() == 'ping':
            self.pong(args[0])

        self._schedule_line()

    def _schedule_line(self):
        self.connection.read_until(b'\n', self.handle_line)

    @gen.coroutine
    def connect(self):
        print('connecting')
        self.connection = yield self.tcp_client_factory.connect('irc.imaginarynet.org.uk', 6667)
        print('connected, initialising')
        yield self._write('NICK butts')
        yield self._write('USER mother 0 * :Your Mother')
        print('done that')
        self._schedule_line()


def main():
    b = IRCClient()
    b.start()
    loopinstance.start()

if __name__ == '__main__':
    import sys
    main(*sys.argv[1:])
