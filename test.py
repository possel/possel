#!/usr/bin/env python
# -*- coding: utf8 -*-
import zmq

from zmq.auth import ioloop as ioauth
from zmq.eventloop import ioloop, zmqstream


def server_pub():
    authenticator = ioauth.IOLoopAuthenticator()
    authenticator.allow('127.0.0.1')
    #authenticator.deny('127.0.0.1')
    socket = zmq.Context.instance().socket(zmq.PUB)
    socket.zap_domain = b'global'
    socket.bind('tcp://*:8080')

    up_socket = zmq.Context.instance().socket(zmq.PAIR)
    up_socket.bind('tcp://*:8081')

    up_stream = zmqstream.ZMQStream(up_socket)

    def up_receive(msg):
        msg = msg[0]
        print('Received: "{}", sending on'.format(msg))
        socket.send(msg)

    up_stream.on_recv(up_receive)

    authenticator.start()
    ioloop.IOLoop.instance().start()


def pusher():
    down_socket = zmq.Context.instance().socket(zmq.PAIR)
    down_socket.connect('tcp://localhost:8081')
    while True:
        msg = bytes(input("Message: "), 'utf8')
        down_socket.send(msg)


def client_sub():
    authenticator = ioauth.IOLoopAuthenticator()
    socket = zmq.Context().instance().socket(zmq.SUB)
    socket.connect('tcp://127.0.0.1:8080')
    socket.setsockopt_string(zmq.SUBSCRIBE, 'butts')

    authenticator.start()
    stream = zmqstream.ZMQStream(socket)
    stream.on_recv(receive)
    ioloop.IOLoop.instance().start()


def receive(msg):
    print(msg)


dispatch = {}
dispatch['client'] = client_sub
dispatch['server'] = server_pub
dispatch['pusher'] = pusher


def main(which):
    ioloop.install()
    dispatch[which]()

if __name__ == '__main__':
    import sys
    main(*sys.argv[1:])
