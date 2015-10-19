__author__ = 'Ralf'

# !/usr/bin/env python

import functools


def count_key_level(x, s, i=0):
    """
    This function counts the level of nested keys.

    :param x: Dictionary to be analyzed.
    :param s: Potential key within the dictionary.
    :param i: Result level.
    :return: Level of nests as a number.
    """
    if s in x.keys():
        return count_key_level(x[s][0], s, i+1)
    else:
        assert isinstance(i, int)
        return i


def key_sequences(d):
    """ Given a (possibly nested) dictionary d, generate tuples giving the
    sequence of keys needed to reach each non-dictionary value in d
    (and its nested sub-dictionaries, if any).

    For example, given the dictionary:

    >>> d = {1: 0, 2: {3: 0, 4: {5: 0}}, 6: 0}

    there are non-dictionary values at d[1], d[2][3], d[2][4][5], and
    d[6], and so:

    >>> sorted(key_sequences(d))
    [(1,), (2, 3), (2, 4, 5), (6,)]

    """
    for k, v in d.items():
        if isinstance(v, dict):
            for seq in key_sequences(v):
                yield (k,) + seq
        else:
            yield (k,)


def get_from_dict(objdict, maplist):
    """
    Gets a value from dictionary objdict according to a key sequence in maplist
    :param objdict: Dictionary containing keys and values
    :param maplist: Map list containing the keys
    :return: Value from dictionary objdict according to a key sequence in maplist
    """
    return functools.reduce(lambda d, k: d[k], maplist, objdict)


def set_from_dict(objdict, maplist, value):
    """
    Sets a value from dictionary objdict according to a key sequence in maplist
    :param objdict: Dictionary containing keys and values
    :param maplist: Map list containing the keys
    :return: Updated dictionary objdict
    """
    get_from_dict(objdict, maplist[:-1])[maplist[-1]] = value