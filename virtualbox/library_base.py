"""This module provides the base types used by library.py

 By Michael Dorman
 [mjdorma+pyvbox@gmail.com]

"""

import re
import inspect
import sys

# Py2 and Py3 compatibility  
try:
    import __builtin__ as builtin 
except:
    import builtins as builtin


def pythonic_name(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    if hasattr(builtin, name) is True or name in ['global']:
        name += "_p"
    return name


class EnumType(type):
    """EnumType is a metaclass for Enum. It is responsible for configuring
    the Enum class object's values defined in Enum.lookup_label"""
    def __init__(cls, name, bases, dct):
        cls._value = None
        cls._lookup_label = {v:l for l, v, _ in cls._enums}
        cls._lookup_doc = {v:d for _, v, d in cls._enums}
        for l, v, _ in cls._enums:
            setattr(cls, pythonic_name(l), cls(v))

    def __getitem__(cls, k):
        if not hasattr(cls, k):
            raise KeyError("%s has no key %s" % cls.__name__, k)
        return getattr(cls, k)


# Code from six - support for py2 and py3 compatibility
def add_metaclass(metaclass):
    """Class decorator for creating a class with a metaclass."""
    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        orig_vars.pop('__dict__', None)
        orig_vars.pop('__weakref__', None)
        slots = orig_vars.get('__slots__')
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper


@add_metaclass(EnumType)   
class Enum(object):
    """Enum objects provide a container for VirtualBox enumerations"""
    _enums = {}
    def __init__(self, value=None):
        if value not in self._lookup_label:
            raise ValueError("Can not find enumeration where value=%s" % value)
        self._value = value
        self.__doc__ = self._lookup_doc[self._value]

    def __str__(self):
        if self._value is None:
            return "None"
        return self._lookup_label[self._value]

    def __int__(self):
        return self._value

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self._value)

    def __eq__(self, k):
        return self.__cmp__(k) == 0

    def __cmp__(self, k):
        return cmp(int(self), int(k))

    def __getitem__(self, k):
        return self.__class__[k]


vbox_error = {}


class VBoxErrorMeta(type):
    def __init__(cls, name, bases, dct):
        global vbox_error
        if cls.value != -1:
            vbox_error[cls.value] = cls


@add_metaclass
class VBoxError(Exception): 
    """Generic VBoxError"""
    name = "undef"
    value = -1
    msg = ""
    def __str__(self):
        return "0x%x (%s)" % (self.value, self.msg)


class Interface(object):
    """Interface objects provide a wrapper for the VirtualBox COM objects"""
    def __init__(self, interface=None):
        if isinstance(interface, Interface):
            import virtualbox 
            manager = virtualbox.Manager()
            self._i = manager.cast_object(interface, self.__class__)._i
        else:
            self._i = interface

    def __nonzero__(self):
        return bool(self._i)

    def _cast_to_valuetype(self, value):
        def cast_to_valuetype(value):
            if isinstance(value, Interface):
                return value._i
            elif isinstance(value, Enum):
                return int(value)
            else:
                return value
        if isinstance(value, list):
            return [cast_to_valuetype(a) for a in value]
        else:
            return cast_to_valuetype(value)

    def _search_attr(self, name, prefix=None):
        attr_name = name
        attr = getattr(self._i, attr_name, None)
        # if a prefix is defined, try to get that prefixed name and use that
        # attribute instead, else, stick with the attr value pulled out above
        if prefix is not None:
            prefix_name = prefix + name[0].upper() + name[1:]
            attr = getattr(self._i, prefix_name, attr)
        if attr is not None:
            return attr
        return None

    def _get_attr(self, name):
        attr = self._search_attr(name, prefix='get')
        if inspect.isfunction(attr) or inspect.ismethod(attr):
            return self._call_method(attr)
        else:
            return attr

    def _set_attr(self, name, value):
        attr = self._search_attr(name, prefix='set')
        if inspect.isfunction(attr) or inspect.ismethod(attr):
            return self._call_method(attr, value)
        else:
            return setattr(self._i, name, value)

    def _call(self, name, in_p=[]):
        global vbox_error
        method = self._search_attr(name)
        if inspect.isfunction(method) or inspect.ismethod(method):
            return self._call_method(method, in_p=in_p)
        else:
            return method

    def _call_method(self, method, in_p=[]):
        in_params = [self._cast_to_valuetype(p) for p in in_p]
        try:
            ret = method(*in_params)
        except Exception as exc:
            if hasattr(exc, 'errno'):
                errno = exc.errno & 0xFFFFFFFF
                errclass = vbox_error.get(errno, VBoxError)
                errobj = errclass()
                errobj.value = errno
            else:
                errobj = VBoxError()
            errobj.msg = getattr(exc, 'msg', exc.message)
            raise errobj
        return ret



