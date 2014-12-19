#!/usr/bin/env python3
# -*- coding: utf8 -*-
import collections

from tornado import gen, ioloop, tcpclient

import possel

loopinstance = ioloop.IOLoop.instance()


class Error(possel.Error):
    """ Root exception for IRC-related exceptions. """


class UnknownNumericCommandError(Error):
    """ Exception thrown when a numeric command is given but no symbolic version can be found. """


class UserNotFoundError(Error):
    """ Exception Thrown when action is performed on non-existant nick.  """


class UserAlreadyExistsError(Error):
    """ Exception Thrown when there is an attempt at overwriting an existing user. """


class UnknownOpcode(Error):
    """ Exception thrown on Unknown Operation Code. """


class KeyDefaultDict(collections.defaultdict):
    def __missing__(self, key):
        if self.default_factory is not None:
            self[key] = self.default_factory(key)
            return self[key]
        else:
            return super(KeyDefaultDict, self).__missing__(key)


def split_irc_line(s):
    """Breaks a message from an IRC server into its prefix, command, and arguments.
    """
    prefix = ''
    trailing = []
    if not s:
        # Raise an exception of some kind
        pass
    if s[0] == ':':
        prefix, s = s[1:].split(' ', 1)
    if s.find(' :') != -1:
        s, trailing = s.split(' :', 1)
        args = s.split()
        args.append(trailing)
    else:
        args = s.split()
    command = args.pop(0)
    return prefix, command, args


def get_nick(who):
    return who.split('!')[0]


def get_symbolic_command(command):
    if command.isdecimal():
        try:
            return numeric_to_symbolic[command]
        except KeyError as e:
            raise UnknownNumericCommandError("No numeric command found: '{}'".format(command)) from e
    else:
        return command


class LineStream:
    def __init__(self):
        self.tcp_client_factory = tcpclient.TCPClient()
        self.line_callback = None
        self.connect_callback = None

    @gen.coroutine
    def connect(self, host, port):
        print('connecting')
        self.connection = yield self.tcp_client_factory.connect(host, port)
        print('connected')
        if self.connect_callback is not None:
            self.connect_callback()
            print('callbacked')
        self._schedule_line()

    def handle_line(self, line):
        if self.line_callback is not None:
            self.line_callback(line)

        self._schedule_line()

    def _schedule_line(self):
        self.connection.read_until(b'\n', self.handle_line)

    def _write(self, line):
        if line[-1] != '\n':
            line += '\n'
        return self.connection.write(line.encode('utf8'))


class IRCServerHandler:
    """ Models a single IRC Server and channels/users on that server.

    Designed to be agnostic to various mechanisms for asynchronous code; you give it a `write_function` callback which
    it will directly call whenever it wants to send things to the server. Then you feed it each line from the IRC server
    by calling `IRCServerHandler.handle_line`.

    Args:
        nick (str): The nick to use for this server.
        write_function: A callback that takes a single string argument and passes it on to the IRC server connection.
    """
    def __init__(self, nick, write_function):
        self._write = write_function
        self.motd = ''
        self.nick = nick

        self.channels = KeyDefaultDict(lambda channel_name: IRCChannel(self._write, channel_name))

    def pong(self, value):
        self._write('PONG :{}'.format(value))

    def pre_line(self):
        self._write('NICK {}'.format(self.nick))
        self._write('USER mother 0 * :Your Mother')

    def handle_line(self, line):
        line = str(line, encoding='utf8').strip()
        (prefix, command, args) = split_irc_line(line)

        try:
            symbolic_command = get_symbolic_command(command)
        except UnknownNumericCommandError:
            pass

        try:
            handler_name = 'on_{}'.format(symbolic_command.lower())
            handler = getattr(self, handler_name)
        except AttributeError:
            self.log_unhandled(symbolic_command, prefix, args)
        else:
            handler(prefix, *args)

    def log_unhandled(self, command, prefix, args):
        print('Unhandled Command received: {} with args ({}) from prefix {}'.format(command, args, prefix))

    # ===============
    # Handlers follow
    # ===============
    def on_ping(self, prefix, token, *args):
        self.pong(token)

    def on_privmsg(self, who_from, to, msg):
        if to.startswith('#'):
            self.channels[to].new_message(get_nick(who_from), msg)

    # ==========
    # JOIN stuff
    def on_join(self, who, channel):
        nick = get_nick(who)
        if nick == self.nick:
            self.self_join(channel)
        else:
            self.channels[channel].user_join(nick)

    def self_join(self, channel):
        pass

    def on_rpl_namreply(self, prefix, recipient, secrecy, channel, names):
        for name in names.split():
            self.channels[channel].user_join(name)

    def on_rpl_endofnames(self, *args):
        pass
    # ==========

    def on_notice(self, prefix, _, message):
        # TODO(moredhel): see whether this is needed...
        print('NOTICE: {}'.format(message))

    def on_mode(self, prefix, channel, op, nick):
        self.channels[channel].user_mode(nick, op)

    def on_quit(self, prefix, message):
        nick = get_nick(prefix)
        if nick != self.nick:
            for channel in self.channels:
                self.channels[channel].user_quit(nick)

    def on_part(self, prefix, channel):
        nick = get_nick(prefix)
        if nick != self.nick:
            self.channels[channel].user_part(nick)

    def on_rpl_welcome(self, *args):
        pass

    def on_rpl_yourhost(self, *args):
        pass

    def on_rpl_created(self, *args):
        pass

    def on_rpl_myinfo(self, *args):
        pass

    def on_rpl_isupport(self, *args):
        # TODO(kitb): Pull the officially supported encoding out of this message
        pass

    def on_rpl_luserclient(self, *args):
        pass

    def on_rpl_luserop(self, *args):
        pass

    def on_rpl_luserchannels(self, *args):
        pass

    def on_rpl_luserme(self, *args):
        pass

    def on_rpl_localusers(self, *args):
        pass

    def on_rpl_globalusers(self, *args):
        pass

    def on_rpl_statsconn(self, *args):
        pass

    def on_rpl_motdstart(self, *args):
        self.motd = ''

    def on_rpl_motd(self, prefix, recipient, motd_line):
        self.motd += motd_line
        self.motd += '\n'

    def on_rpl_endofmotd(self, *args):
        print(self.motd)

    # =============
    # Handlers done
    # =============

    def join_channel(self, channel, password=None):
        if password:
            self._write('JOIN {} {}'.format(channel, password))
        else:
            self._write('JOIN {}'.format(channel))


class User:
    def __init__(self, name):
        self.name = name
        self.modes = set()

    def split_mode(self, mode):
        # TODO(moredhel): wrap this in a try catch? as I'm assuming my input is at least 2 chars long
        return mode[0], mode[1]

    def mode_change(self, mode):
        """ Either adds or removes the Input Mode, by parsing the text and seeing what is required """
        direction, op = self.split_mode(mode)
        if direction == '+':
            self.modes[op]
        elif direction == '-' and op in self.modes:
            del self.modes[op]
        else:
            raise UnknownOpcode(
                'UnknownOpcode "{}", expecting "-" or "+"'.format(op)
            )

    def mode_get(self, mode=None):
        if mode in self.modes:
            return set(self.modes[mode])
        return self.modes


class IRCChannel:
    def __init__(self, write_function, name):
        self._write = write_function
        self.name = name
        self.nicks = dict()
        self.messages = []

    def user_mode(self, nick, mode):
        if nick not in self.nicks:
            raise UserNotFoundError(
                'Tried to Change Op of user to "{}", but "{}" does not exist on channel "{}"'
                .format(mode, nick, self.name)
            )
        self.nicks[nick].mode_change(mode)

    def user_join(self, nick):
        if nick in self.nicks:
            raise UserAlreadyExistsError(
                'Tried to add user "{}" to channel {}'.format(nick, self.name)
            )
        self.nicks[nick] = User(nick)

    def user_quit(self, nick):
        # TODO(moredhel): make sure I'm doing it right
        if nick in self.nicks:
            del self.nicks[nick]

    def user_part(self, nick):
        try:
            del self.nicks[nick]
        except KeyError as e:
            raise UserNotFoundError(
                'Tried to remove non-existent nick "{}" from channel {}'.format(nick, self.name)) from e

    def new_message(self, who_from, msg):
        self.messages.append((who_from, msg))
        if msg.startswith('!d listmessages'):
            print(self.messages)
        elif msg.startswith('!d listusers'):
            print(self.nicks)


symbolic_to_numeric = {
    "RPL_WELCOME": '001',
    "RPL_YOURHOST": '002',
    "RPL_CREATED": '003',
    "RPL_MYINFO": '004',
    "RPL_ISUPPORT": '005',
    "RPL_BOUNCE": '010',
    "RPL_STATSCONN": '250',
    "RPL_LOCALUSERS": '265',
    "RPL_GLOBALUSERS": '266',
    "RPL_USERHOST": '302',
    "RPL_ISON": '303',
    "RPL_AWAY": '301',
    "RPL_UNAWAY": '305',
    "RPL_NOWAWAY": '306',
    "RPL_WHOISUSER": '311',
    "RPL_WHOISSERVER": '312',
    "RPL_WHOISOPERATOR": '313',
    "RPL_WHOISIDLE": '317',
    "RPL_ENDOFWHOIS": '318',
    "RPL_WHOISCHANNELS": '319',
    "RPL_WHOWASUSER": '314',
    "RPL_ENDOFWHOWAS": '369',
    "RPL_LISTSTART": '321',
    "RPL_LIST": '322',
    "RPL_LISTEND": '323',
    "RPL_UNIQOPIS": '325',
    "RPL_CHANNELMODEIS": '324',
    "RPL_NOTOPIC": '331',
    "RPL_TOPIC": '332',
    "RPL_INVITING": '341',
    "RPL_SUMMONING": '342',
    "RPL_INVITELIST": '346',
    "RPL_ENDOFINVITELIST": '347',
    "RPL_EXCEPTLIST": '348',
    "RPL_ENDOFEXCEPTLIST": '349',
    "RPL_VERSION": '351',
    "RPL_WHOREPLY": '352',
    "RPL_ENDOFWHO": '315',
    "RPL_NAMREPLY": '353',
    "RPL_ENDOFNAMES": '366',
    "RPL_LINKS": '364',
    "RPL_ENDOFLINKS": '365',
    "RPL_BANLIST": '367',
    "RPL_ENDOFBANLIST": '368',
    "RPL_INFO": '371',
    "RPL_ENDOFINFO": '374',
    "RPL_MOTDSTART": '375',
    "RPL_MOTD": '372',
    "RPL_ENDOFMOTD": '376',
    "RPL_YOUREOPER": '381',
    "RPL_REHASHING": '382',
    "RPL_YOURESERVICE": '383',
    "RPL_TIME": '391',
    "RPL_USERSSTART": '392',
    "RPL_USERS": '393',
    "RPL_ENDOFUSERS": '394',
    "RPL_NOUSERS": '395',
    "RPL_TRACELINK": '200',
    "RPL_TRACECONNECTING": '201',
    "RPL_TRACEHANDSHAKE": '202',
    "RPL_TRACEUNKNOWN": '203',
    "RPL_TRACEOPERATOR": '204',
    "RPL_TRACEUSER": '205',
    "RPL_TRACESERVER": '206',
    "RPL_TRACESERVICE": '207',
    "RPL_TRACENEWTYPE": '208',
    "RPL_TRACECLASS": '209',
    "RPL_TRACERECONNECT": '210',
    "RPL_TRACELOG": '261',
    "RPL_TRACEEND": '262',
    "RPL_STATSLINKINFO": '211',
    "RPL_STATSCOMMANDS": '212',
    "RPL_ENDOFSTATS": '219',
    "RPL_STATSUPTIME": '242',
    "RPL_STATSOLINE": '243',
    "RPL_UMODEIS": '221',
    "RPL_SERVLIST": '234',
    "RPL_SERVLISTEND": '235',
    "RPL_LUSERCLIENT": '251',
    "RPL_LUSEROP": '252',
    "RPL_LUSERUNKNOWN": '253',
    "RPL_LUSERCHANNELS": '254',
    "RPL_LUSERME": '255',
    "RPL_ADMINME": '256',
    "RPL_ADMINLOC": '257',
    "RPL_ADMINLOC": '258',
    "RPL_ADMINEMAIL": '259',
    "RPL_TRYAGAIN": '263',
    "ERR_NOSUCHNICK": '401',
    "ERR_NOSUCHSERVER": '402',
    "ERR_NOSUCHCHANNEL": '403',
    "ERR_CANNOTSENDTOCHAN": '404',
    "ERR_TOOMANYCHANNELS": '405',
    "ERR_WASNOSUCHNICK": '406',
    "ERR_TOOMANYTARGETS": '407',
    "ERR_NOSUCHSERVICE": '408',
    "ERR_NOORIGIN": '409',
    "ERR_NORECIPIENT": '411',
    "ERR_NOTEXTTOSEND": '412',
    "ERR_NOTOPLEVEL": '413',
    "ERR_WILDTOPLEVEL": '414',
    "ERR_BADMASK": '415',
    "ERR_UNKNOWNCOMMAND": '421',
    "ERR_NOMOTD": '422',
    "ERR_NOADMININFO": '423',
    "ERR_FILEERROR": '424',
    "ERR_NONICKNAMEGIVEN": '431',
    "ERR_ERRONEUSNICKNAME": '432',
    "ERR_NICKNAMEINUSE": '433',
    "ERR_NICKCOLLISION": '436',
    "ERR_UNAVAILRESOURCE": '437',
    "ERR_USERNOTINCHANNEL": '441',
    "ERR_NOTONCHANNEL": '442',
    "ERR_USERONCHANNEL": '443',
    "ERR_NOLOGIN": '444',
    "ERR_SUMMONDISABLED": '445',
    "ERR_USERSDISABLED": '446',
    "ERR_NOTREGISTERED": '451',
    "ERR_NEEDMOREPARAMS": '461',
    "ERR_ALREADYREGISTRED": '462',
    "ERR_NOPERMFORHOST": '463',
    "ERR_PASSWDMISMATCH": '464',
    "ERR_YOUREBANNEDCREEP": '465',
    "ERR_YOUWILLBEBANNED": '466',
    "ERR_KEYSET": '467',
    "ERR_CHANNELISFULL": '471',
    "ERR_UNKNOWNMODE": '472',
    "ERR_INVITEONLYCHAN": '473',
    "ERR_BANNEDFROMCHAN": '474',
    "ERR_BADCHANNELKEY": '475',
    "ERR_BADCHANMASK": '476',
    "ERR_NOCHANMODES": '477',
    "ERR_BANLISTFULL": '478',
    "ERR_NOPRIVILEGES": '481',
    "ERR_CHANOPRIVSNEEDED": '482',
    "ERR_CANTKILLSERVER": '483',
    "ERR_RESTRICTED": '484',
    "ERR_UNIQOPPRIVSNEEDED": '485',
    "ERR_NOOPERHOST": '491',
    "ERR_NOSERVICEHOST": '492',
    "ERR_UMODEUNKNOWNFLAG": '501',
    "ERR_USERSDONTMATCH": '502',
}
numeric_to_symbolic = {v: k for k, v in symbolic_to_numeric.items()}


def main():
    import argparse

    # Parse the CLI args
    arg_parser = argparse.ArgumentParser(description='Possel IRC Client Server')
    arg_parser.add_argument('-n', '--nick', default='possel',
                            help='Nick to use on the server.')
    arg_parser.add_argument('-s', '--server', default='irc.imaginarynet.org.uk',
                            help='IRC Server to connect to')
    arg_parser.add_argument('-c', '--channel', default='#possel-test',
                            help='Channel to join on server')
    args = arg_parser.parse_args()

    # Create instances
    line_stream = LineStream()
    server = IRCServerHandler(args.nick, line_stream._write)

    # Attach instances
    line_stream.connect_callback = server.pre_line
    line_stream.line_callback = server.handle_line

    # Connect
    line_stream.connect(args.server, 6667)

    # Join a channel
    loopinstance.call_later(2, server.join_channel, args.channel)

    # GOGOGOGO
    loopinstance.start()

if __name__ == '__main__':
    main()
