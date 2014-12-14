#!/usr/bin/env python
# -*- coding: utf8 -*-
import os.path

from setuptools import setup

install_requires = ['tornado',
                    'pyzmq']

classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Topic :: Communications :: Chat :: Internet Relay Chat',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python :: 3 :: Only',
]

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme_file:
    long_description = readme_file.read()

setup(
    # Metadata
    name='possel-server',
    version='0.0.1',
    packages=['possel'],
    author='Kit Barnes',
    author_email='kit@ninjalith.com',
    description='Python-based IRC "bouncer", requires custom clients for scrollback.',
    long_description=long_description,
    url='https://bitbucket.org/KitB/possel/',
    license='BSD',
    keywords='irc quassel',
    classifiers=classifiers,

    # Non-metadata (mostly)
    py_modules=[],
    zip_safe=False,
    install_requires=install_requires,
    extras_require={},
    scripts=['bin/possel'],
    package_data={},
)
