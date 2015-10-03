#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import logging

from pircel import model, tornado_adapter

logger = logging.getLogger(__name__)


commands = {'join',
            'query',
            'me',
            'nick',
            'connect',
            }


def parse_args(parser, parsee, buffer):
    try:
        args = parser.parse_args(parsee[0].split())
    except (SystemExit, IndexError):
        model.create_line(buffer=buffer, content='=' * 80, kind='other', nick='-*-')
        for line in parser.format_help().splitlines():
            model.create_line(buffer=buffer, content=line, kind='other', nick='-*-')
        model.create_line(buffer=buffer, content='=' * 80, kind='other', nick='-*-')
        return False
    else:
        return args


class Dispatcher:
    def __init__(self, interfaces):
        self.interfaces = interfaces

    def dispatch(self, buffer_id, line):
        if line.startswith('/'):
            line = line[1:]
        command, *rest = line.split(maxsplit=1)
        command = command.lower()

        if command in commands:
            buffer = model.IRCBufferModel.get(id=buffer_id)
            getattr(self, command)(buffer, rest)

    def join(self, buffer, rest):
        parser = argparse.ArgumentParser(prog='join')
        parser.add_argument('channel', help='The channel to join')
        parser.add_argument('password', default=None, nargs='?',
                            help='Optional password for the channel')

        args = parse_args(parser, rest, buffer)
        if not args:
            return

        interface = self.interfaces[buffer.server.id]
        interface.server_handler.join(args.channel, args.password)

    def query(self, buffer, rest):
        parser = argparse.ArgumentParser(prog='query')
        parser.add_argument('who', help='Who to open a query buffer with')

        args = parse_args(parser, rest, buffer)
        if not args:
            return

        model.ensure_buffer(args.who, buffer.server)

    def me(self, buffer, rest):
        line = rest[0]
        interface = self.interfaces[buffer.server.id]
        interface.server_handler.send_message(buffer.name, '\1ACTION {}\1'.format(line))

    def nick(self, buffer, rest):
        new_nick = rest[0]
        interface = self.interfaces[buffer.server.id]
        interface.server_handler.change_nick(new_nick)

    def connect(self, buffer, rest):
        parser = argparse.ArgumentParser(prog='connect')
        parser.add_argument('-s', '--secure', action='store_true',
                            help='Enable ssl/tls for this server')
        parser.add_argument('-p', '--port', default=6697,
                            help='The port to connect on')
        user = buffer.server.user
        parser.add_argument('-n', '--nick', default=user.nick,
                            help='The nick to use on this server')
        parser.add_argument('-r', '--realname', default=user.realname,
                            help='The real name to use on this server')
        parser.add_argument('-u', '--username', default=user.username,
                            help='The username to use on this server')
        parser.add_argument('host', help='The server to connect to')

        args = parse_args(parser, rest, buffer)
        if not args:
            return

        server = model.create_server(host=args.host,
                                     port=args.port,
                                     secure=args.secure,
                                     nick=args.nick,
                                     realname=args.realname,
                                     username=args.username)

        interface = model.IRCServerInterface(server)
        tornado_adapter.IRCClient.from_interface(interface).connect()
        self.interfaces[interface.server_model.id] = interface


def main():
    pass

if __name__ == '__main__':
    main()
