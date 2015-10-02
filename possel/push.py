#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pircel import model
import tornado.websocket


class ResourcePusher(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def send_line_id(self, _, line, server):
        self.write_message({'type': 'line', 'line': line.id})

    def send_buffer_id(self, _, buffer, server):
        self.write_message({'type': 'buffer', 'buffer': buffer.id, 'server': server.id})

    def send_user_id(self, _, user, server):
        self.write_message({'type': 'user', 'user': user.id, 'server': server.id})

    def send_server_id(self, _, server):
        self.write_message({'type': 'server', 'server': server.id})

    def send_membership(self, _, membership, user, buffer):
        self.write_message({'type': 'membership', 'membership': membership.id, 'user': user.id, 'buffer': buffer.id})

    def initialize(self, interfaces):
        self.interfaces = interfaces
        self.signals = {model.new_line: self.send_line_id,
                        model.new_buffer: self.send_buffer_id,
                        model.new_user: self.send_user_id,
                        model.new_server: self.send_server_id,
                        model.new_membership: self.send_membership,
                        }

    def open(self):
        for signal, handler in self.signals.items():
            model.signal_factory(signal).connect(handler)

    def on_close(self):
        for signal, handler in self.signals.items():
            model.signal_factory(signal).disconnect(handler)


def main():
    pass

if __name__ == '__main__':
    main()
