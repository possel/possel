# -*- coding: utf-8 -*-
"""
possel.resources
----------------

This module defines a tornado-based RESTful (? - I don't know shit about REST) API for fetching the state of the possel
system over HTTP. This is coupled with a real time push mechanism that will be used to inform the client of new
resources.
"""

import json

from pircel import model, tornado_adapter
import tornado.web


class BaseAPIHandler(tornado.web.RequestHandler):
    def initialize(self, controllers):
        self.set_header('Content-Type', 'application/json')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers', 'Content-Type')
        self.controllers = controllers

    def prepare(self):
        if self.request.headers.get('Content-Type', '').startswith('application/json'):
            self.json = json.loads(self.request.body.decode())

    def get_body_argument_tuple(self, names):
        return [self.get_body_argument(name) for name in names]


class LinesHandler(BaseAPIHandler):
    def get(self):
        line_id = self.get_argument('id', None)
        before = self.get_argument('before', None)
        after = self.get_argument('after', None)
        kind = self.get_argument('kind', None)
        last = self.get_argument('last', False)

        if not (line_id or before or after or last):
            raise tornado.web.HTTPError(403)

        lines = model.IRCLineModel.select()
        if line_id is not None:
            lines = lines.where(model.IRCLineModel.id == line_id)
        if before is not None:
            lines = lines.where(model.IRCLineModel.id <= before)
        if after is not None:
            lines = lines.where(model.IRCLineModel.id >= after)
        if kind is not None:
            lines = lines.where(model.IRCLineModel.kind == kind)
        if last:
            lines = lines.order_by(-model.IRCLineModel.id).limit(1)

        self.write(json.dumps([line.to_dict() for line in lines]))

    def post(self):
        buffer_id = self.json['buffer']
        content = self.json['content']

        buffer = model.IRCBufferModel.get(id=buffer_id)
        controller = self.controllers[buffer.server_id]

        controller.server_handler.send_message(buffer.name, content)


class BufferGetHandler(BaseAPIHandler):
    def get(self, buffer_id):
        buffers = model.IRCBufferModel.select()
        if buffer_id != 'all':
            buffers = buffers.where(model.IRCBufferModel.id == buffer_id)

        self.write(json.dumps([buffer.to_dict() for buffer in buffers]))


class BufferPostHandler(BaseAPIHandler):
    def post(self):
        server_id = self.json['server']
        name = self.json['name']

        assert name[0] in '#&+!', 'Not given a channel as buffer'

        controller = self.controllers[server_id]
        controller.server_handler.join(name)


class ServerGetHandler(BaseAPIHandler):
    def get(self, server_id):
        servers = model.IRCServerModel.select()
        if server_id != 'all':
            servers = servers.where(model.IRCServerModel.id == server_id)

        self.write(json.dumps([server.to_dict() for server in servers]))


class ServerPostHandler(BaseAPIHandler):
    def post(self):
        j = self.json
        user = model.UserDetails.create(nick=j['nick'], realname=j['realname'], username=j['username'])

        server = model.IRCServerModel.create(host=j['host'], port=j['port'], secure=j['secure'], user=user)

        controller = model.IRCServerController(server)
        tornado_adapter.IRCClient.from_controller(controller).connect()
        self.controllers[server.id] = controller


class UserGetHandler(BaseAPIHandler):
    def get(self, user_id):
        users = model.IRCUserModel.select()
        if user_id != 'all':
            users = users.where(model.IRCUserModel.id == user_id)

        self.write(json.dumps([user.to_dict() for user in users]))
