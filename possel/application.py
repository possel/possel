#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

import peewee
from pircel import model, tornado_adapter
import tornado.ioloop
import tornado.web
from tornado.web import url

from possel import push, resources, web_client


def get_routes(controllers):
    controller_routes = [url(r'/line', resources.LinesHandler),
                         url(r'/buffer/([0-9+]|all)', resources.BufferGetHandler),
                         url(r'/buffer', resources.BufferPostHandler),
                         url(r'/server/([0-9+]|all)', resources.ServerGetHandler),
                         url(r'/server', resources.ServerPostHandler),
                         url(r'/user/([0-9+]|all)', resources.UserGetHandler),
                         url(r'/push', push.ResourcePusher, name='push'),
                         ]
    for route in controller_routes:
        route.kwargs.update(controllers=controllers)

    routes = [url(r'/', web_client.WebUIServer, name='index'),
              ] + controller_routes
    print(routes)
    return routes


def get_relative_path(path):
    """ Gets the path of a file under the current directory """
    file_directory = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(file_directory, path)

settings = {'template_path': get_relative_path('data/templates'),
            'static_path': get_relative_path('data/static'),
            'debug': True,
            }


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

    application = tornado.web.Application(get_routes(controllers), **settings)
    application.listen(8080)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
