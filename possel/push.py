#!/usr/bin/env python
# -*- coding: utf-8 -*-
import tornado.websocket


class ResourcePusher(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def send_line_id(self, line_id):
        self.write_message(str(line_id))

    def initialize(self, controllers):
        self.controllers = controllers

    def open(self):
        # Attach all the callbacks
        for controller in self.controllers.values():
            controller.add_callback(controller.new_line, self.send_line_id)

    def on_close(self):
        # Detach all the callbacks
        for controller in self.controllers.values():
            controller.remove_callback(controller.new_line, self.send_line_id)


def main():
    pass

if __name__ == '__main__':
    main()
