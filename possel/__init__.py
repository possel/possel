import logbook
__version__ = '0.2.2'


class Error(Exception):
    """ Root exception for all custom exceptions in possel. """


VALID_ADAPTERS = {
    'tornado': 'possel.adapter.tornado',
    'asyncio': 'possel.adapter.asyncio',
}


def _exc_exit(unused_callback):
    import sys
    import traceback
    traceback.print_exc()
    sys.exit(1)


def get_arg_parser():
    import argparse
    arg_parser = argparse.ArgumentParser(description='Possel IRC Client Server')
    arg_parser.add_argument('-n', '--nick', default='possel',
                            help='Nick to use on the server.')
    arg_parser.add_argument('-u', '--username', default='possel',
                            help='Username to use on the server')
    arg_parser.add_argument('-r', '--real-name', default='Possel IRC',
                            help='Real name to use on the server')
    arg_parser.add_argument('-s', '--server', default='irc.imaginarynet.org.uk',
                            help='IRC Server to connect to')
    arg_parser.add_argument('-c', '--channel', action='append',
                            help='Channel to join on server')
    arg_parser.add_argument('-D', '--debug', action='store_true',
                            help='Enable debug logging')
    arg_parser.add_argument('--die-on-exception', action='store_true',
                            help='Exit program when an unhandled exception occurs, rather than trying to recover')
    arg_parser.add_argument('--debug-out-loud', action='store_true',
                            help='Print selected debug messages out over IRC')
    arg_parser.add_argument('-a', '--adapter', default='tornado', choices=VALID_ADAPTERS.keys(),
                            help='Which async adapter to use.')
    return arg_parser


def get_parsed_args():
    arg_parser = get_arg_parser()
    args = arg_parser.parse_args()

    if not args.channel:
        args.channel = ['#possel-test']

    return args


def main():
    import importlib

    from possel import irc
    args = get_parsed_args()

    # setup logging
    log_handler = logbook.StderrHandler(level=logbook.DEBUG if args.debug else logbook.INFO)

    # Get server handler
    server_handler = irc.IRCServerHandler(irc.User(args.nick, args.username, args.real_name), args.debug_out_loud)

    # Get adapter and connect
    adapter = importlib.import_module(VALID_ADAPTERS[args.adapter])
    adapter.connect(args, server_handler)

    with log_handler.applicationbound():
        adapter.main_loop()
