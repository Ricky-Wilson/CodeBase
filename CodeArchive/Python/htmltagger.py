from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from future import standard_library

standard_library.install_aliases()
from builtins import *


def tag(name, data="", **kw):
    attrs = " ".join(('{}="{}"'.format(k, v) for k, v in list(kw.items())))
    if not attrs:
        return "<{name}>{data}</{name}>".format(name=name, data=data)
    if kw:
        return "\n<{name} {attrs}>{data}</{name}>\n".format(
            data=data, name=name, attrs=attrs
        )
