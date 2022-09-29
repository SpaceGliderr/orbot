from functools import reduce


def get_from_dict(dic, map_list):
    """Iterate nested dictionary"""
    try:
        return reduce(dict.get, map_list, dic)
    except TypeError:
        return None


def dict_has_key(dic, key):
    return key in dic.keys()
