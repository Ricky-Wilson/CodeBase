import abc
import json
from urllib import error
from posixpath import join as urljoin

from uaclient import config
from uaclient import util
from uaclient import version

try:
    from typing import Optional, Type  # noqa
except ImportError:
    # typing isn't available on trusty, so ignore its absence
    pass


class UAServiceClient(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def api_error_cls(self) -> 'Type[Exception]':
        """Set in subclasses to the type of API error raised"""
        pass

    @property
    @abc.abstractmethod
    def cfg_url_base_attr(self) -> str:
        """String in subclasses, the UAConfig attribute containing base url"""
        pass

    def __init__(self, cfg: 'Optional[config.UAConfig]' = None) -> None:
        if not cfg:
            self.cfg = config.UAConfig()
        else:
            self.cfg = cfg

    def headers(self):
        return {'user-agent': 'UA-Client/%s' % version.get_version(),
                'accept': 'application/json',
                'content-type': 'application/json'}

    def request_url(self, path, data=None, headers=None, method=None):
        path = path.lstrip('/')
        if not headers:
            headers = self.headers()
        if headers.get('content-type') == 'application/json' and data:
            data = json.dumps(data).encode('utf-8')
        url = urljoin(getattr(self.cfg, self.cfg_url_base_attr), path)
        try:
            response, headers = util.readurl(
                url=url, data=data, headers=headers, method=method)
        except error.URLError as e:
            code = e.errno
            if hasattr(e, 'read'):
                error_details = util.maybe_parse_json(e.read().decode('utf-8'))
                if error_details:
                    raise self.api_error_cls(e, error_details)
            raise util.UrlError(e, code=code, headers=headers, url=url)
        return response, headers
