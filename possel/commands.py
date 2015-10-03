#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

from pircel import model

logger = logging.getLogger(__name__)


commands = {'join',
            'query',
            'me',
            'nick',
            }


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
        words = rest[0].split()
        channel = words[0]
        password = words[1] if len(words) > 1 else None

        interface = self.interfaces[buffer.server.id]
        interface.server_handler.join(channel, password)

    def query(self, buffer, rest):
        words = rest[0].split()
        who = words[0]
        model.ensure_buffer(who, buffer.server)

    def me(self, buffer, rest):
        line = rest[0]
        interface = self.interfaces[buffer.server.id]
        interface.server_handler.send_message(buffer.name, '\1ACTION {}\1'.format(line))

    def nick(self, buffer, rest):
        new_nick = rest[0]
        interface = self.interfaces[buffer.server.id]
        interface.server_handler.change_nick(new_nick)


def main():
    pass

if __name__ == '__main__':
    main()
