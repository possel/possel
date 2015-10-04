#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import datetime
import logging
import os

import cryptography.exceptions
from cryptography.hazmat import backends
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf import pbkdf2
import peewee as p
from pircel import model


logger = logging.getLogger(__name__)


def cryptographically_strong_random_token():
    return base64.urlsafe_b64encode(os.urandom(20))


class UserModel(model.BaseModel):
    username = p.TextField(unique=True)
    password = p.TextField()
    salt = p.TextField()


class TokenModel(model.BaseModel):
    user = p.ForeignKeyField(UserModel, related_name='tokens', on_delete='CASCADE')
    token = p.TextField(unique=True)
    expiry_date = p.DateTimeField()


def create_tables():
    model.database.create_tables([UserModel, TokenModel], safe=True)


def get_kdf(salt):
    kdf = pbkdf2.PBKDF2HMAC(algorithm=hashes.SHA224,
                            length=32,
                            salt=salt,
                            iterations=100000,
                            backend=backends.default_backend(),
                            )
    return kdf


def hash_password(salt, password):
    if not isinstance(salt, bytes):
        salt = salt.encode()
    if not isinstance(password, bytes):
        password = password.encode()

    kdf = get_kdf(salt)
    return base64.urlsafe_b64encode(kdf.derive(password)).decode()


def verify_password(salt, password, expected_hash):
    if not isinstance(salt, bytes):
        salt = salt.encode()
    if not isinstance(password, bytes):
        password = password.encode()
    if not isinstance(expected_hash, bytes):
        expected_hash = expected_hash.encode()
    expected_hash = base64.urlsafe_b64decode(expected_hash)

    kdf = get_kdf(salt)
    kdf.verify(password, expected_hash)


def set_password(user, password, save=True):
    salt = base64.urlsafe_b64encode(os.urandom(20))
    hash = hash_password(salt, password)

    user.salt = salt
    user.password = hash
    if save:
        user.save()


def create_user(username, password):
    user = UserModel(username=username)
    set_password(user, password, False)
    user.save()


def check_password(username, password):
    try:
        user = UserModel.get(username=username)
    except p.DoesNotExist:
        return None

    try:
        verify_password(user.salt, password, user.password)
    except cryptography.exceptions.InvalidKey:
        return None
    else:
        return user


def cleanup_tokens():
    TokenModel.delete().where(TokenModel.expiry_date < datetime.datetime.utcnow())


def delete_token(token):
    TokenModel.get(token=token).delete_instance()


def get_new_token(user):
    token = None
    while token is None:
        try:
            token = TokenModel.create(token=cryptographically_strong_random_token(),
                                      user=user,
                                      expiry_date=datetime.datetime.utcnow() + datetime.timedelta(days=30),
                                      )
        except p.IntegrityError:
            # Holy balls a collision happened, let the loop try again
            pass

    return token.token


def get_user_by_token(token_string):
    cleanup_tokens()
    try:
        token = TokenModel.get(token=token_string)
    except p.DoesNotExist:
        return None
    else:
        return token.user


class LoginFailed(Exception):
    pass


def login_get_token(username, password, old_token):
    user = check_password(username, password)
    if user is not None:
        # successful login, get them a new token and revoke an existing old one
        if old_token is not None and get_user_by_token(old_token) == user:
            delete_token(old_token)
        new_token = get_new_token(user)
        return new_token
    raise LoginFailed()


def main():
    import argparse
    from playhouse import db_url
    parser = argparse.ArgumentParser(description='Add a user to the database')
    parser.add_argument('-d', '--database', help='Peewee database selector', default='sqlite:///possel.db')
    parser.add_argument('username', help='The username to add')
    parser.add_argument('password', help='The password to add')
    args = parser.parse_args()

    db = db_url.connect(args.database)
    model.database.initialize(db)
    model.initialize()
    create_tables()

    try:
        create_user(args.username, args.password)
    except p.IntegrityError:
        print('User already exists')
    else:
        print('User successfully created')

if __name__ == '__main__':
    main()
