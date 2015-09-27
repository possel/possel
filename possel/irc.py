#!/usr/bin/env python3
# -*- coding: utf8 -*-
import collections
import pprint

import chardet
import logbook

import possel

logger = logbook.Logger(__name__)


class Error(possel.Error):
    """ Root exception for IRC-related exceptions. """


class UnknownNumericCommandError(Error):
    """ Exception thrown when a numeric command is given but no symbolic version can be found. """


class UserNotFoundError(Error):
    """ Exception Thrown when action is performed on non-existant nick.  """


class UserAlreadyExistsError(Error):
    """ Exception Thrown when there is an attempt at overwriting an existing user. """


class UnknownModeCommandError(Error):
    """ Exception thrown on unknown mode change command. """


class KeyDefaultDict(collections.defaultdict):
    def __missing__(self, key):
        if self.default_factory is not None:
            self[key] = self.default_factory(key)
            return self[key]
        else:
            return super(KeyDefaultDict, self).__missing__(key)


def split_irc_line(s):
    """Breaks a message from an IRC server into its prefix, command, and arguments.

    Copied straight from twisted, license and copyright for this function follows:
    Copyright (c) 2001-2014
    Allen Short
    Andy Gayton
    Andrew Bennetts
    Antoine Pitrou
    Apple Computer, Inc.
    Ashwini Oruganti
    Benjamin Bruheim
    Bob Ippolito
    Canonical Limited
    Christopher Armstrong
    David Reid
    Donovan Preston
    Eric Mangold
    Eyal Lotem
    Google Inc.
    Hybrid Logic Ltd.
    Hynek Schlawack
    Itamar Turner-Trauring
    James Knight
    Jason A. Mobarak
    Jean-Paul Calderone
    Jessica McKellar
    Jonathan Jacobs
    Jonathan Lange
    Jonathan D. Simms
    Jürgen Hermann
    Julian Berman
    Kevin Horn
    Kevin Turner
    Laurens Van Houtven
    Mary Gardiner
    Matthew Lefkowitz
    Massachusetts Institute of Technology
    Moshe Zadka
    Paul Swartz
    Pavel Pergamenshchik
    Ralph Meijer
    Richard Wall
    Sean Riley
    Software Freedom Conservancy
    Travis B. Hartwell
    Thijs Triemstra
    Thomas Herve
    Timothy Allen
    Tom Prince

    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
    rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
    Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
    WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
    OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
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


def parse_identity(who):
    nick, rest = who.split('!')
    username, host = rest.split('@')

    if username.startswith('~'):
        username = username[1:]

    return nick, username, host


def get_symbolic_command(command):
    if command.isdecimal():
        try:
            return numeric_to_symbolic[command]
        except KeyError as e:
            raise UnknownNumericCommandError("No numeric command found: '{}'".format(command)) from e
    else:
        return command


class IRCServerHandler:
    """ Models a single IRC Server and channels/users on that server.

    Designed to be agnostic to various mechanisms for asynchronous code; you give it a `write_function` callback which
    it will directly call whenever it wants to send things to the server. Then you feed it each line from the IRC server
    by calling `IRCServerHandler.handle_line`.

    Args:
        nick (str): The nick to use for this server.
        write_function: A callback that takes a single string argument and passes it on to the IRC server connection.
    """
    def __init__(self, identity, debug_out_loud=False):
        # Useful things
        self._write = None
        self.identity = identity

        # Default values
        self.motd = ''

        self.channels = KeyDefaultDict(lambda channel_name: IRCChannel(self._write, channel_name,
                                                                       debug_out_loud=debug_out_loud,
                                                                       identity=identity))

        self.users = dict()
        self.users[identity.nick] = identity

        self.callbacks = collections.defaultdict(set)

        # Configurables
        self._debug_out_loud = debug_out_loud

    def get_user_full(self, who):
        nick, username, host = parse_identity(who)
        try:
            user = self.users[nick]
            if not user.fully_known:
                user.username = username
                user.fully_known = True
            return user
        except KeyError:
            self.users[nick] = User(nick, username)
            self.users[nick].fully_known = True
            return self.users[nick]

    def get_user_by_nick(self, nick):
        try:
            return self.users[nick]
        except KeyError:
            self.users[nick] = User(nick)
            return self.users[nick]

    def add_callback(self, signal, callback):
        self.callbacks[signal].add(callback)

    @property
    def write_function(self):
        return self._write

    @write_function.setter
    def write_function(self, new_write_function):
        self._write = new_write_function

    def pong(self, value):
        self._write('PONG :{}'.format(value))

    def pre_line(self):
        self._write('NICK {}'.format(self.identity.nick))
        self._write('USER {} 0 * :{}'.format(self.identity.username, self.identity.real_name))

    def handle_line(self, line):
        try:
            line = str(line, encoding='utf8')
        except UnicodeDecodeError:
            logger.debug('UTF8 decode failed, bytes: {}', line)
            encoding = chardet.detect(line)['encoding']
            logger.debug('Tried autodetecting and got {}, decoding now', encoding)
            line = str(line, encoding=encoding)
        line = line.strip()
        (prefix, command, args) = split_irc_line(line)

        try:
            symbolic_command = get_symbolic_command(command)
        except UnknownNumericCommandError:
            self.log_unhandled(command, prefix, args)
            return

        try:
            handler_name = 'on_{}'.format(symbolic_command.lower())
            handler = getattr(self, handler_name)
        except AttributeError:
            self.log_unhandled(symbolic_command, prefix, args)
        else:
            handler(prefix, *args)

        for callback in self.callbacks[symbolic_command.lower()]:
            callback(self, prefix, *args)

    def log_unhandled(self, command, prefix, args):
        logger.warning('Unhandled Command received: {} with args ({}) from prefix {}'.format(command, args, prefix))

    # ===============
    # Handlers follow
    # ===============
    def on_ping(self, prefix, token, *args):
        logger.debug('Ping received: {}, {}', prefix, token)
        self.pong(token)

    def on_privmsg(self, who_from, to, msg):
        if to.startswith('#'):
            user = self.get_user_full(who_from)
            self.channels[to].on_new_message(user, msg)

    # ==========
    # JOIN stuff
    def on_join(self, who, channel):
        user = self.get_user_full(who)
        if user is self.identity:
            self.self_join(channel)
        else:
            self.channels[channel].user_join(user)

    def self_join(self, channel):
        pass

    def on_rpl_namreply(self, prefix, recipient, secrecy, channel, nicks):
        for nick in nicks.split():
            user = self.get_user_by_nick(nick)
            self.channels[channel].user_join(user)

    def on_rpl_endofnames(self, *args):
        pass
    # ==========

    def on_notice(self, prefix, _, message):
        logger.info('NOTICE: {}'.format(message))

    def on_mode(self, prefix, channel, command, nick):
        user = self.get_user_by_nick(nick)
        user.apply_mode_command(channel, command)

    def on_nick(self, who, new_nick):
        user = self.get_user_full(who)
        logger.debug('User {} changed nick to {}', user.nick, new_nick)
        del self.users[user.nick]
        user.name = new_nick
        self.users[new_nick] = user

    def on_quit(self, who, message):
        user = self.get_user_full(who)
        if user != self.identity:
            for channel in self.channels:
                try:
                    self.channels[channel].user_part(user)
                except UserNotFoundError:
                    pass

    def on_part(self, who, channel):
        user = self.get_user_full(who)
        if user != self.identity:
            self.channels[channel].user_part(user)

    def on_rpl_welcome(self, *args):
        pass

    def on_rpl_yourhost(self, *args):
        pass

    def on_rpl_created(self, *args):
        pass

    def on_rpl_myinfo(self, *args):
        pass

    def on_rpl_isupport(self, *args):
        logger.debug('Server supports: {}', args)

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
        logger.info(self.motd)

    # =============
    # Handlers done
    # =============


class User:
    def __init__(self, name, username=None, real_name=None, password=None):
        self.name = name
        self.username = username or name
        self.real_name = real_name or name
        self.modes = collections.defaultdict(set)
        self.fully_known = False

    @property
    def nick(self):
        return self.name

    def apply_mode_command(self, channel, command):
        """ Applies a mode change command.

        Similar syntax to the `chmod` program.
        """
        direction, mode = command
        if direction == '+':
            self.modes[channel].add(mode)
        elif direction == '-' and mode in self.modes:
            self.modes[channel].remove(mode)
        else:
            raise UnknownModeCommandError('Unknown mode change command "{}", expecting "-" or "+"'.format(command))

    def __str__(self):
        modes = {}
        for m in self.modes.values():
            modes |= m

        return '{}!{} +{}'.format(self.name, self.username,
                                  ''.join(modes))

    def __repr__(self):
        return str(self)


class IRCChannel:
    def __init__(self, write_function, name, identity, debug_out_loud=False):
        self._write = write_function
        self.name = name
        self.identity = identity
        self.users = set()
        self.messages = []

        self._debug_out_loud = debug_out_loud

    def user_join(self, user):
        logger.debug('{} joined {}', user, self.name)
        if user.nick in self.users:
            raise UserAlreadyExistsError(
                'Tried to add user "{}" to channel {}'.format(user.nick, self.name)
            )
        self.users.add(user)

    def user_part(self, user):
        logger.debug('{} parted from {}', user, self.name)
        try:
            self.users.remove(user)
        except KeyError as e:
            raise UserNotFoundError(
                'Tried to remove non-existent nick "{}" from channel {}'.format(user.nick, self.name)) from e

    def on_new_message(self, who_from, msg):
        self.messages.append((who_from, msg))

        if msg.startswith('!d listmessages'):
            logger.debug(self.messages)

            if self._debug_out_loud:
                self.send_message(self.messages)

        elif msg.startswith('!d listusers'):
            logger.debug(self.users)

            if self._debug_out_loud:
                self.send_message(pprint.pformat(self.users))

        elif msg.startswith('!d raise'):
            raise Error('Debug exception')

    def join(self, password=None):
        if password:
            self._write('JOIN {} {}'.format(self.name, password))
        else:
            self._write('JOIN {}'.format(self.name))

    def part(self):
        pass

    def send_message(self, message):
        if not isinstance(message, (str, bytes)):
            message = str(message)
        for line in message.split('\n'):
            self.messages.append((self.identity, line))
            self._write('PRIVMSG {} :{}'.format(self.name, line))


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
