#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pircel import model
import tornado.websocket


class ResourcePusher(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def send_line_id(self, controller, line):
        self.write_message({'type': 'line', 'line': line})

    def send_buffer_id(self, controller, buffer):
        self.write_message({'type': 'buffer', 'buffer': buffer, 'server': controller.server_model.id})

    def initialize(self, controllers):
        self.controllers = controllers

    def open(self):
        model.signal_factory(model.new_line).connect(self.send_line_id)

    def on_close(self):
        model.signal_factory(model.new_line).disconnect(self.send_line_id)


def main():
    pass

if __name__ == '__main__':
    main()
