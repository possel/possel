#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pircel.model
------------

This module defines an API for storing the state of an IRC server and probably includes some database bits too.
"""
import collections
import datetime
import logging

import peewee as p
from playhouse import shortcuts

import pircel
from pircel import protocol, signals

logger = logging.getLogger(__name__)
signal_factory = signals.namespace('model')


class Error(pircel.Error):
    """ Root exception for model related exceptions.

    e.g. Exceptions which are thrown when there is a state mismatch. """


class UserNotFoundError(Error):
    """ Exception Thrown when action is performed on non-existent nick.  """


class UserAlreadyExistsError(Error):
    """ Exception Thrown when there is an attempt at overwriting an existing user. """


class ModeNotFoundError(Error):
    """ Exception thrown when we try to remove a mode that a user doesn't have. """


class ServerAlreadyAttachedError(Error):
    """ Exception thrown when someone tries to attach a server handler to a server interface that already has one. """


class KeyDefaultDict(collections.defaultdict):
    """ defaultdict modification that provides the key to the factory. """
    def __missing__(self, key):
        if self.default_factory is not None:
            self[key] = self.default_factory(key)
            return self[key]
        else:
            return super(KeyDefaultDict, self).__missing__(key)


database = p.Proxy()


class BaseModel(p.Model):
    class Meta:
        database = database

    def to_dict(self):
        return shortcuts.model_to_dict(self, recurse=False)


class UserDetails(BaseModel):
    """ Models all details that are pertinent to every user.

    Users that are connected to a server should use IRCUserModel, this is only really for defining our own details (e.g.
    so we can send the "NICK ..." message at initial connection).
    """
    nick = p.CharField()
    realname = p.TextField(null=True)
    username = p.TextField(null=True)


class IRCServerModel(BaseModel):
    """ Models an IRC server, including how to connect to it.

    Does *not* reference networks yet, if ever.
    """
    # =========================================================================
    # Connection Details
    # ------------------
    #
    # Standard IRC connection stuff.
    #
    # Doesn't interact with protocol objects; interesting to note?
    # =========================================================================
    host = p.TextField()
    port = p.IntegerField(default=6697)  # You're damn right we default to SSL
    secure = p.BooleanField(default=True)
    # =========================================================================

    # =========================================================================
    # User Details
    # ------------
    #
    # Who *we* are on this server.
    # =========================================================================
    user = p.ForeignKeyField(UserDetails)
    # =========================================================================

    class Meta:
        indexes = ((('host', 'port'), True),
                   )


class IRCUserModel(UserDetails):
    """ Models users that are connected to an IRC Server.

    Inherits most of its fields from UserDetails.

    Don't delete user models, they're needed for line models.
    """
    host = p.TextField(null=True)  # where they're coming from
    server = p.ForeignKeyField(IRCServerModel, related_name='users', on_delete='CASCADE')
    current = p.BooleanField()  # are they connected?

    class Meta:
        indexes = ((('server', 'nick'), False),
                   (('server', 'nick', 'current'), True),
                   )


class IRCBufferModel(BaseModel):
    """ Models anything that will store a bunch of messages and maybe have some people in it.

    This means channels and PMs.
    """
    name = p.TextField()  # either a channel '#channel' or a nick 'nick'
    server = p.ForeignKeyField(IRCServerModel, related_name='buffers', on_delete='CASCADE')

    class Meta:
        indexes = ((('name', 'server'), True),
                   )


line_types = [('message', 'Message'),
              ('notice', 'Notice'),
              ('join', 'Join'),
              ('part', 'Part'),
              ('quit', 'Quit'),
              ('nick', 'Nick Change'),
              ('action', 'Action'),
              ('other', 'Other'),
              ]  # TODO: Consider more/less line types? Line types as display definitions?


class IRCLineModel(BaseModel):
    """ Models anything that might be displayed in a buffer.

    Typically this will be messages, notices, CTCP ACTIONs, joins, quits, mode changes, topic changes, etc.
    """
    # Where
    buffer = p.ForeignKeyField(IRCBufferModel, related_name='lines', on_delete='CASCADE')

    # Who and when
    timestamp = p.DateTimeField(default=datetime.datetime.now)
    user = p.ForeignKeyField(IRCUserModel, null=True, on_delete='CASCADE')  # Can have lines with no User displayed
    nick = p.TextField(null=True)  # We store the nick of the user at the time of the message

    # What
    kind = p.CharField(max_length=20, default='message', choices=line_types)
    content = p.TextField()

    def to_dict(self):
        d = shortcuts.model_to_dict(self, recurse=False)
        d['timestamp'] = d['timestamp'].replace(tzinfo=datetime.timezone.utc).timestamp()
        return d


class IRCBufferMembershipRelation(BaseModel):
    """ Buffers and Users have a many-to-many relationship, this handles that. """
    buffer = p.ForeignKeyField(IRCBufferModel, related_name='memberships', on_delete='CASCADE')
    user = p.ForeignKeyField(IRCUserModel, related_name='memberships', on_delete='CASCADE')

    class Meta:
        indexes = ((('buffer', 'user'), True),
                   )


def create_tables():
    database.create_tables([UserDetails,
                            IRCServerModel,
                            IRCUserModel,
                            IRCBufferModel,
                            IRCLineModel,
                            IRCBufferMembershipRelation,
                            ], safe=True)


# Callback signal definitions
new_user = 'new_user'
new_line = 'new_line'
new_buffer = 'new_buffer'
new_server = 'new_server'
new_membership = 'new_membership'
deleted_membership = 'deleted_membership'


# =========================================================================
# Controller functions
# ------------------
#
# Because we really don't need a controller class for this
# =========================================================================
def create_user(nick, server, current=True, realname=None, username=None, host=None):
    user = IRCUserModel.create(nick=nick, realname=realname, username=username, host=host, server=server,
                               current=current)
    signal_factory(new_user).send(None, user=user, server=user.server)
    return user


def update_user(old_nick, server, nick=None, realname=None, username=None, host=None, current=None):
    user = IRCUserModel.get(nick=old_nick, server=server)

    if nick is not None:
        user.nick = nick

    if realname is not None:
        user.realname = realname

    if username is not None:
        user.username = username

    if host is not None:
        user.host = host

    if current is not None:
        user.current = current

    user.save()
    signal_factory(new_user).send(None, user=user, server=user.server)
    return user


def create_line(buffer, content, kind, user=None, nick=None):
    if nick is not None:
        line = IRCLineModel.create(buffer=buffer, content=content, kind=kind, user=user, nick=nick)
    elif user is not None:
        line = IRCLineModel.create(buffer=buffer, content=content, kind=kind, user=user, nick=user.nick)
    else:
        line = IRCLineModel.create(buffer=buffer, content=content, kind=kind, user=user)
    server = line.buffer.server
    signal_factory(new_line).send(None, line=line, server=server)
    return line


def create_buffer(name, server):
    buffer = IRCBufferModel.create(name=name, server=server)
    signal_factory(new_buffer).send(None, buffer=buffer, server=buffer.server)
    return buffer


def create_membership(buffer, user):
    membership = IRCBufferMembershipRelation.create(buffer=buffer, user=user)
    signal_factory(new_membership).send(None, membership=membership, buffer=buffer, user=user)
    return membership


def delete_membership(user, buffer):
    membership = IRCBufferMembershipRelation.get(user=user, buffer=buffer)
    membership.delete_instance()
    signal_factory(deleted_membership).send(None, membership=membership)


def create_server(host, port, secure, nick, realname, username):
    user = UserDetails.create(nick=nick, realname=realname, username=username)
    server = IRCServerModel.create(host=host, port=port, secure=secure, user=user)
    signal_factory(new_server).send(None, server=server)
    return server
# =========================================================================


# =========================================================================
# Access functions
# ----------------
#
# Not calling them "view" because they can modify stuff
# =========================================================================
def ensure_user(nick, server, realname=None, username=None, host=None):
    """ Gets a user by (nick, server) and updates the other properties. """
    try:
        user = create_user(nick=nick, server=server)
    except p.IntegrityError:
        user = IRCUserModel.get(nick=nick, server=server)

    changed = False
    if realname is not None:
        user.realname = realname
        changed = True
    if username is not None:
        user.username = username
        changed = True
    if host is not None:
        user.host = host
        changed = True
    if changed:
        user.save()

    return user


def ensure_buffer(name, server):
    try:
        buffer = create_buffer(name=name, server=server)
    except p.IntegrityError:
        buffer = IRCBufferModel.get(name=name, server=server)
    return buffer


def ensure_membership(buffer, user):
    try:
        membership = create_membership(buffer, user)
    except p.IntegrityError:
        membership = IRCBufferMembershipRelation.get(buffer=buffer, user=user)
    return membership
# =========================================================================


class IRCServerInterface:
    def __init__(self, server_model):
        self.server_model = server_model
        self._user = server_model.user
        self._server_handler = None
        self.protocol_callbacks = {'privmsg': self._handle_privmsg,
                                   'join': self._handle_join,
                                   'part': self._handle_part,
                                   'rpl_namreply': self._handle_rpl_namreply,
                                   'nick': self._handle_nick
                                   }

    @property
    def server_handler(self):
        return self._server_handler

    @server_handler.setter
    def server_handler(self, new_server_handler):
        if self._server_handler is not None:
            raise ServerAlreadyAttachedError()

        for signal, callback in self.protocol_callbacks.items():
            new_server_handler.add_callback(signal, callback)

        self._server_handler = new_server_handler

    # =========================================================================
    # Handlers
    # --------
    #
    # Callbacks that will be attached to the protocol handler.
    #
    # Callbacks all pass the server handler itself as the first argument, we
    # ignore it because we already have it, hence the "_" argument in all of
    # these.
    # =========================================================================
    def _handle_join(self, _, **kwargs):
        who = kwargs['prefix']
        channel, = kwargs['args']
        nick, username, host = protocol.parse_identity(who)

        buffer = ensure_buffer(channel, self.server_model)

        if nick == self._user.nick:  # *We* are joining a channel
            pass
        else:  # Someone is joining a channel we're already in
            user = ensure_user(nick=nick,
                               username=username,
                               host=host,
                               server=self.server_model)
            ensure_membership(buffer, user)
            create_line(buffer=buffer, user=user, kind='join', content='has joined the channel')

    def _handle_privmsg(self, _, **kwargs):
        who_from = kwargs['prefix']
        to, msg = kwargs['args']
        nick, username, host = protocol.parse_identity(who_from)

        if to == self._user.nick:  # Private Message
            buffer = ensure_buffer(name=nick, server=self.server_model)
        else:  # Hopefully a channel message?
            buffer = ensure_buffer(name=to, server=self.server_model)

        user = ensure_user(nick=nick, server=self.server_model)
        action_prefix = '\1ACTION '
        kind = 'message'
        if msg.startswith(action_prefix):
            msg = msg[len(action_prefix):-1]
            kind = 'action'

        create_line(buffer=buffer, user=user, kind=kind, content=msg)

    def _handle_rpl_namreply(self, _, **kwargs):
        to, channel_privacy, channel, space_sep_names = kwargs['args']
        names = space_sep_names.split(' ')
        buffer = ensure_buffer(name=channel, server=self.server_model)
        for name in names:
            user = self.get_user_by_nick(name)
            ensure_membership(user=user, buffer=buffer)

    def _handle_nick(self, _, **kwargs):
        old_nick, username, host = protocol.parse_identity(kwargs['prefix'])
        new_nick, *other_args = kwargs['args']  # shouldn't be any other args

        logger.debug('%s, %s', old_nick, self.server_handler.identity.nick)

        if new_nick == self.server_handler.identity.nick:
            # The protocol handler will update its own state as it uses the database model without saving it for storage
            # We save it because we're the database bit.
            # We want to wait until confirmation that the nick change happens from the server.
            self.server_handler.identity.save()

        try:
            user = update_user(old_nick, self.server_model, nick=new_nick)
        except p.IntegrityError:
            # The *IRC Server* has told us this nick change is occurring, we can safely assume no one is currently using
            # the nick
            update_user(new_nick, self.server_model, current=False)
            user = update_user(old_nick, self.server_model, nick=new_nick)

        for relation in user.memberships:
            buffer = relation.buffer
            create_line(buffer=buffer,
                        user=user,
                        nick=old_nick,
                        kind='nick',
                        content='is now known as {}'.format(new_nick))

    def _handle_part(self, _, **kwargs):
        nick, username, host = protocol.parse_identity(kwargs['prefix'])
        channel, *other_args = kwargs['args']

        user = IRCUserModel.get(nick=nick, server=self.server_model)
        buffer = IRCBufferModel.get(name=channel, server=self.server_model)

        delete_membership(user, buffer)
        create_line(buffer=buffer, user=user, kind='part', content='has left the channel')
    # =========================================================================

    # =========================================================================
    # Helper methods
    # --------------
    #
    # Yes, normally we don't do getters in Python but these have parameters.
    # =========================================================================
    def get_user_by_nick(self, nick):
        """ Return the user object from just the nick.

        Args:
            nick (str): Either the nick or the nick with a channel mode prefix.
        """
        # Pull @ or + off the front
        # I checked the RFC; these should be the only two chars
        # We can later use these to determine modes
        if nick[0] in '@+':
            nick = nick[1:]

        user = ensure_user(nick=nick, server=self.server_model)
        return user

    @property
    def connection_details(self):
        m = self.server_model
        return m.host, m.port, m.secure

    @property
    def identity(self):
        return self._user

    @property
    def channels(self):
        n = IRCBufferModel.name
        return self.server_model.buffers.where(n.startswith('#') |
                                               n.startswith('&') |
                                               n.startswith('+') |
                                               n.startswith('!'))
    # =========================================================================

    # =========================================================================
    # Constructors / Factories
    # =========================================================================
    @classmethod
    def new(cls, host, port, secure, user):
        server_model = create_server(host=host, port=port, secure=secure, user=user)
        return cls(server_model)

    @classmethod
    def get(cls, host, port):
        server_model = IRCServerModel.get(host=host, port=port)
        return cls(server_model)

    @classmethod
    def get_all(cls):
        models = IRCServerModel.select()
        return {model.id: cls(model) for model in models}
    # =========================================================================


def main():
    pass

if __name__ == '__main__':
    main()
