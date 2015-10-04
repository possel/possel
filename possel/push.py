# -*- coding: utf-8 -*-
import logging

from pircel import model
from tornado import websocket
import tornado.web

from possel import auth


logger = logging.getLogger(__name__)


class ResourcePusher(websocket.WebSocketHandler):
    def get_current_user(self):
        token = self.get_secure_cookie('token')
        if token is None:
            return None
        return auth.get_user_by_token(token)

    @tornado.web.asynchronous
    def get(self, *args, **kwargs):
        if not self.get_current_user():
            self.set_status(401)
            self.finish('Unauthorized.')
            return
        super(ResourcePusher, self).get(*args, **kwargs)

    def check_origin(self, origin):
        return True

    def send_last_line_id(self):
        try:
            line = model.IRCLineModel.select().order_by(-model.IRCLineModel.id).limit(1)[0]
        except IndexError:
            self.write_message({'type': 'last_line', 'line': -1})
        else:
            self.write_message({'type': 'last_line', 'line': line.id})

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

    def send_deleted_membership(self, _, membership):
        self.write_message({'type': 'delete_membership', 'membership': membership.to_dict()})

    def initialize(self, interfaces):
        self.interfaces = interfaces
        self.signals = {model.new_line: self.send_line_id,
                        model.new_buffer: self.send_buffer_id,
                        model.new_user: self.send_user_id,
                        model.new_server: self.send_server_id,
                        model.new_membership: self.send_membership,
                        model.delete_membership: self.send_deleted_membership,
                        }

    def open(self):
        for signal, handler in self.signals.items():
            model.signal_factory(signal).connect(handler)
        self.send_last_line_id()

    def on_close(self):
        for signal, handler in self.signals.items():
            model.signal_factory(signal).disconnect(handler)
