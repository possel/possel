# -*- coding: utf-8 -*-
"""
possel.resources
----------------

This module defines a tornado-based RESTful (? - I don't know shit about REST) API for fetching the state of the possel
system over HTTP. This is coupled with a real time push mechanism that will be used to inform the client of new
resources.
"""

import json
import logging

from pircel import model, tornado_adapter
import tornado.web

from possel import auth, commands

logger = logging.getLogger(__name__)


class BaseAPIHandler(tornado.web.RequestHandler):
    def initialize(self, interfaces):
        self.set_header('Content-Type', 'application/json')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers', 'Content-Type')
        self.interfaces = interfaces

    def prepare(self):
        if self.request.headers.get('Content-Type', '').startswith('application/json'):
            self.json = json.loads(self.request.body.decode())

    def get_body_argument_tuple(self, names):
        return [self.get_body_argument(name) for name in names]

    def get_current_user(self):
        token_string = self.get_secure_cookie('token')
        if token_string is None:
            return None
        user = auth.get_user_by_token(token_string)
        if user is None:
            self.clear_cookie('token')
        return user


class SessionHandler(BaseAPIHandler):
    def post(self):
        j = self.json
        try:
            token = auth.login_get_token(j['username'], j['password'], self.get_secure_cookie('token'))
        except auth.LoginFailed:
            raise tornado.web.HTTPError(401)
        else:
            self.set_secure_cookie('token', token)
            self.write({})

    def get(self):
        if not self.get_current_user():
            raise tornado.web.HTTPError(401)
        # Used to verify tokens
        self.write({})


class LinesHandler(BaseAPIHandler):
    def initialize(self, *args, **kwargs):
        super(LinesHandler, self).initialize(*args, **kwargs)
        self.dispatcher = commands.Dispatcher(self.interfaces)

    @tornado.web.authenticated
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

    @tornado.web.authenticated
    def post(self):
        buffer_id = self.json['buffer']
        content = self.json['content']

        if content[0] == '/':
            logger.debug('Slash line: %s', content)
            self.dispatcher.dispatch(buffer_id, content)
        else:
            buffer = model.IRCBufferModel.get(id=buffer_id)
            interface = self.interfaces[buffer.server_id]

            interface.server_handler.send_message(buffer.name, content)

        # javascript needs this to write something, otherwise it doesn't
        # handle it as a success.
        self.write({})


class BufferGetHandler(BaseAPIHandler):
    @tornado.web.authenticated
    def get(self, buffer_id):
        buffers = model.IRCBufferModel.select()
        if buffer_id != 'all':
            buffers = buffers.where(model.IRCBufferModel.id == buffer_id)

        self.write(json.dumps([buffer.to_dict() for buffer in buffers]))


class BufferPostHandler(BaseAPIHandler):
    @tornado.web.authenticated
    def post(self):
        server_id = self.json['server']
        name = self.json['name']

        assert name[0] in '#&+!', 'Not given a channel as buffer'

        interface = self.interfaces[server_id]
        interface.server_handler.join(name)

        self.write({})


class ServerGetHandler(BaseAPIHandler):
    @tornado.web.authenticated
    def get(self, server_id):
        servers = model.IRCServerModel.select()
        if server_id != 'all':
            servers = servers.where(model.IRCServerModel.id == server_id)

        self.write(json.dumps([server.to_dict() for server in servers]))


class ServerPostHandler(BaseAPIHandler):
    @tornado.web.authenticated
    def post(self):
        j = self.json

        server = model.create_server(host=j['host'],
                                     port=j['port'],
                                     secure=j['secure'],
                                     nick=j['nick'],
                                     realname=j['realname'],
                                     username=j['username'])

        interface = model.IRCServerInterface(server)
        tornado_adapter.IRCClient.from_interface(interface).connect()
        self.interfaces[interface.server_model.id] = interface

        self.write({})


class UserGetHandler(BaseAPIHandler):
    @tornado.web.authenticated
    def get(self, user_id):
        users = model.IRCUserModel.select()
        if user_id != 'all':
            users = users.where(model.IRCUserModel.id == user_id)

        buffer = self.get_argument('buffer', None)
        if buffer is not None:
            buffer = int(buffer)
            users = (users
                     .join(model.IRCBufferMembershipRelation)
                     .where(model.IRCBufferMembershipRelation.buffer == buffer))

        self.write(json.dumps([user.to_dict() for user in users]))
