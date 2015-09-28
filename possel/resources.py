#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
possel.resources
----------------

This module defines a tornado-based RESTful (? - I don't know shit about REST) API for fetching the state of the possel
system over HTTP. This is coupled with a real time push mechanism that will be used to inform the client of new
resources.
"""

import json

import peewee
from pircel import model, tornado_adapter
import tornado.ioloop
import tornado.web
from tornado.web import url


class BaseAPIHandler(tornado.web.RequestHandler):
    def initialize(self, controllers):
        self.set_header('Content-Type', 'application/json')
        self.controllers = controllers


class LinesHandler(BaseAPIHandler):
    def get(self):
        line_id = self.get_argument('id', None)
        before = self.get_argument('before', None)
        after = self.get_argument('after', None)
        kind = self.get_argument('kind', None)

        if not (line_id or before or after):
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

        self.write(json.dumps([line.to_dict() for line in lines]))

    def post(self):
        buffer_id = self.get_body_argument('buffer')
        content = self.get_body_argument('content')

        buffer = model.IRCBufferModel.get(id=buffer_id)
        controller = self.controllers[buffer.server_id]

        controller.server_handler.send_message(buffer.name, content)


def main():
    db = peewee.SqliteDatabase('imaginary.db')
    model.database.initialize(db)
    model.database.connect()
    model.create_tables()

    controllers = model.IRCServerController.get_all()
    clients = {controller_id: tornado_adapter.IRCClient.from_controller(controller)
               for controller_id, controller in controllers.items()}
    for client in clients.values():
        client.connect()

    application = tornado.web.Application([url(r'/lines', LinesHandler, dict(controllers=controllers)),
                                           ])
    application.listen(8080)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
