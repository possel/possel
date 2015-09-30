__version__ = '0.2.2'

from possel import application

main = application.main


class Error(Exception):
    """ Root exception for all custom exceptions in possel. """
