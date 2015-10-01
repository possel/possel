#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import os

from pircel import model, tornado_adapter

from playhouse import db_url

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
    return routes


def get_relative_path(path):
    """ Gets the path of a file under the current directory """
    file_directory = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(file_directory, path)

settings = {'template_path': get_relative_path('data/templates'),
            'static_path': get_relative_path('data/static'),
            }


def get_arg_parser():
    arg_parser = argparse.ArgumentParser(description='Possel Server')
    arg_parser.add_argument('-d', '--database', default='sqlite:///possel.db',
                            help='sqlalchemy-style database url string. See '
                            'http://peewee.readthedocs.org/en/latest/peewee/playhouse.html#db-url '
                            'for specification.')
    arg_parser.add_argument('-p', '--port', default=80,
                            help='Port possel server will listen on')
    arg_parser.add_argument('-b', '--bind-address', default='',
                            help='Address possel server will listen on (e.g. 0.0.0.0 for IPv4)')
    arg_parser.add_argument('-D', '--debug', action='store_true',
                            help='Turn on debug logging and show exceptions in the browser')
    return arg_parser


def main():
    args = get_arg_parser().parse_args()

    db = db_url.connect(args.database)
    model.database.initialize(db)
    model.database.connect()
    model.create_tables()

    controllers = model.IRCServerController.get_all()
    clients = {controller_id: tornado_adapter.IRCClient.from_controller(controller)
               for controller_id, controller in controllers.items()}
    for client in clients.values():
        client.connect()

    settings['debug'] = args.debug

    application = tornado.web.Application(get_routes(controllers), **settings)
    application.listen(args.port, args.bind_address)

    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
