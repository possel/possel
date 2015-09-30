#!/usr/bin/env python
# -*- coding: utf-8 -*-
import peewee
from pircel import model, tornado_adapter
import tornado.ioloop
import tornado.web
from tornado.web import url

from possel import push, resources


def get_routes(controllers):
    routes = [(r'/line', resources.LinesHandler),
              (r'/buffer/([0-9+]|all)', resources.BufferGetHandler),
              (r'/buffer', resources.BufferPostHandler),
              (r'/server/([0-9+]|all)', resources.ServerGetHandler),
              (r'/server', resources.ServerPostHandler),
              (r'/push', push.ResourcePusher),
              ]
    routes = [route + ({'controllers': controllers},) for route in routes]
    return [url(*route) for route in routes]


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

    application = tornado.web.Application(get_routes(controllers))
    application.listen(8080)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
