#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pircel.model
------------

This module defines an API for storing the state of an IRC server and probably includes some database bits too.
"""
import collections
import functools
import logging

import peewee as p

import pircel
from pircel import protocol

logger = logging.getLogger(__name__)


class Error(pircel.Error):
    """ Root exception for model related exceptions.

    e.g. Exceptions which are thrown when there is a state mismatch. """


class UserNotFoundError(Error):
    """ Exception Thrown when action is performed on non-existent nick.  """


class UserAlreadyExistsError(Error):
    """ Exception Thrown when there is an attempt at overwriting an existing user. """


class ModeNotFoundError(Error):
    """ Exception thrown when we try to remove a mode that a user doesn't have. """


class KeyDefaultDict(collections.defaultdict):
    """ defaultdict modification that provides the key to the factory. """
    def __missing__(self, key):
        if self.default_factory is not None:
            self[key] = self.default_factory(key)
            return self[key]
        else:
            return super(KeyDefaultDict, self).__missing__(key)


class IRCServerModel(p.Model):
    pass


class IRCServerController(object):
    def __init__(self, server_model):
        pass

    def get_user_full(self, who):
        """ Return the User object for a given IRC identity string, creating if necessary.

        Args:
            who (str): Full IRC identity string (as specified in §2.3.1 of rfc2812, second part of "prefix" definition)
                       of the user
        Returns:
            A User object with a nick property that is unique between this method and `get_user_by_nick`; e.g.
            subsequent calls of either with the same *nick* part will result in the same object being returned.
        """
        nick, username, host = protocol.parse_identity(who)
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

    def get_user_by_nick(self, nick, channel=None):
        """ Return the user object from just the nick.

        Will also parse "@nick" or "+nick" properly, and set the mode if the channel is provided.

        Args:
            nick (str): Either the nick or the nick with a channel mode prefix.
            channel (str): The name of the channel if this is being called from a 'RPL_NAMREPLY' callback.
        Returns:
            A User object for the specified nick; this object will be unique by nick if only this method and
            `get_user_full` are used to get User objects.
        """
        # Pull @ or + off the front
        # I checked the RFC; these should be the only two chars
        mode = None
        if nick[0] in '@+':
            mode = nick[0]
            nick = nick[1:]

        # Get or create and get the user object
        try:
            user = self.users[nick]
        except KeyError:
            self.users[nick] = User(nick)
            user = self.users[nick]

        # Set +o or +v if we need to
        if channel is not None and mode is not None:
            mode = {'@': 'o', '+': 'v'}[mode]  # Look it up in a local dict
            user.modes[channel].add(mode)

        return user

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
        """ Sent when you join a channel or run /names """
        for nick in nicks.split():
            user = self.get_user_by_nick(nick, channel)
            self.channels[channel].user_join(user)

    def on_rpl_endofnames(self, *args):
        """ Sent when we're done with rpl_namreply messages """
        pass
    # ==========

    def on_notice(self, prefix, _, message):
        logger.info('NOTICE: %s', message)

    def on_mode(self, prefix, channel, command, nick):
        user = self.get_user_by_nick(nick)
        user.apply_mode_command(channel, command)

    def on_nick(self, who, new_nick):
        user = self.get_user_full(who)
        logger.debug('User %s changed nick to %s', user.nick, new_nick)
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

    def on_privmsg(self, who_from, to, msg):
        if to.startswith('#'):
            user = self.get_user_full(who_from)
            self.channels[to].on_new_message(user, msg)

    def on_rpl_isupport(self, *args):
        logger.debug('Server supports: %s', args)

    def on_rpl_motdstart(self, *args):
        self.motd = ''

    def on_rpl_motd(self, prefix, recipient, motd_line):
        self.motd += motd_line
        self.motd += '\n'

    def on_rpl_endofmotd(self, *args):
        logger.info(self.motd)
        self.who('0')

    def on_rpl_whoreply(self, prefix, recipient, channel, user, host, server, nick, *args):
        # the last parameter will always be there, there are a bunch of optionals in between
        *args, hopcount_and_realname = args

        hopcount, realname = hopcount_and_realname.split(' ', maxsplit=1)
        user = self.get_user_full('{}!{}@{}'.format(nick, user, host))
        user.real_name = realname
    # =============
    # Handlers done
    # =============


@functools.total_ordering
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
        elif mode not in self.modes:
            raise ModeNotFoundError(
                'User "{}" doesn\'t have mode "{}" that we were told to remove'.format(self.name, mode))
        else:
            raise protocol.UnknownModeCommandError('Unknown mode change command'
                                                   ' "{}", expecting "-" or "+"'.format(command))

    def __str__(self):
        modes = set()
        for m in self.modes.values():
            modes |= m

        if self.fully_known:
            modes.add('&')

        return '{}!{} +{}'.format(self.name, self.username,
                                  ''.join(modes))

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    def __gt__(self, other):
        return self.name > other.name

    def __hash__(self):
        return hash(self.name)


class IRCChannel:
    def __init__(self, name, server, debug_out_loud=False):
        self.server = server
        self._write = server.write_function
        self.name = name
        self.identity = server.identity
        self.users = set()
        self.messages = []

        self._debug_out_loud = debug_out_loud

    def user_join(self, user):
        logger.debug('%s joined %s', user, self.name)
        if user.nick in self.users:
            raise UserAlreadyExistsError(
                'Tried to add user "{}" to channel {}'.format(user.nick, self.name)
            )
        self.users.add(user)

    def user_part(self, user):
        logger.debug('%s parted from %s', user, self.name)
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
            logger.debug(self.server.users)

            if self._debug_out_loud:
                for user in sorted(self.server.users.values()):
                    self.send_message(user)

        elif msg.startswith('!d raise'):
            raise Error('Debug exception')

    def part(self):
        pass

    def send_message(self, message):
        if not isinstance(message, (str, bytes)):
            message = str(message)
        for line in message.split('\n'):
            self.messages.append((self.identity, line))
            self._write('PRIVMSG {} :{}'.format(self.name, line))


def main():
    pass

if __name__ == '__main__':
    main()
