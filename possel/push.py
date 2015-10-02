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

    def initialize(self, interfaces):
        self.interfaces = interfaces

    def open(self):
        model.signal_factory(model.new_line).connect(self.send_line_id)
        model.signal_factory(model.new_buffer).connect(self.send_buffer_id)

    def on_close(self):
        model.signal_factory(model.new_line).disconnect(self.send_line_id)
        model.signal_factory(model.new_buffer).disconnect(self.send_buffer_id)


def main():
    pass

if __name__ == '__main__':
    main()
