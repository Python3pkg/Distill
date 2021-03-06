import cgi
import json
import re
from routes import URLGenerator
from distill.helpers import cached_property, parse_query_string, CaseInsensitiveDict, text_


class Request(object):
    _cookiere = re.compile(r'([^=]+)=([^;]+)(?:;\s*)*')

    def __init__(self, env, app=None):
        """ Init
         Notes:
            Parses all relavent environ variables and stores
            them on the request

        Args:
            env: The wsgi environ variable
            app: The application's instance
        """

        self.settings = app.settings.copy()
        self.env = env
        self.url = URLGenerator(app.map, env)
        self.session = None
        self.resp_callbacks = []

        self.stream = env['wsgi.input']
        self.errors = env['wsgi.errors']
        self.scheme = env['wsgi.url_scheme']

        path = env['PATH_INFO']
        if path:
            if len(path) != 1 and path.endswith("/"):
                self.path = path[:-1]
            else:
                self.path = path
        else:
            self.path = "/"

        if 'CONTENT_TYPE' in env:
            self.content_type = env['CONTENT_TYPE']
        elif 'HTTP_CONTENT_TYPE' in env:
            self.content_type = env['HTTP_CONTENT_TYPE']
        else:
            self.content_type = None
        if 'CONTENT_LENGTH' in env and env['CONTENT_LENGTH']:
            self.content_length = int(env['CONTENT_LENGTH'])
        else:
            self.content_length = 0

        if 'QUERY_STRING' in env and env['QUERY_STRING']:
            self.GET = parse_query_string(env['QUERY_STRING'])
        else:
            self.GET = {}
        if self.content_type and "application/x-www-form-urlencoded" in self.content_type:
            data = self.stream.read(self.content_length)
            self.POST = parse_query_string(data)
        elif self.content_type and 'multipart/form-data' in self.content_type:
            fs_env = self.env.copy()
            fs_env.setdefault('CONTENT_LENGTH', '0')
            fs_env['QUERY_STRING'] = ''
            self.POST = cgi.FieldStorage(fp=self.stream, environ=fs_env, keep_blank_values=True)
            self.POST = dict([(field.name, field.value) if field.filename is None
                              else (field.name, field) for field in self.POST.list])
        else:
            self.POST = {}
            if self.stream is not None:
                self.body = self.stream.read(self.content_length)

    @cached_property()
    def headers(self):
        """ Returns the HTTP headers present in the request

         Notes:
            Headers are cached permanently and should not be
            modified.
        """
        headers = CaseInsensitiveDict()
        for k, v in list(self.env.items()):
            if k.startswith("HTTP_"):
                headers[k[5:].replace('_', '-')] = v

        return headers

    @cached_property()
    def json_body(self):
        return json.loads(text_(self.body))

    @cached_property()
    def cookies(self):
        # noinspection PyTypeChecker
        return dict(self._cookiere.findall(self.headers.get('Cookie', '')))

    @property
    def server(self):
        """Returns the server name, including port"""
        if 'HTTP_HOST' in self.env:
            return self.env['HTTP_HOST']
        else:
            return "{0}:{1}".format(self.env['SERVER_NAME'], self.port)

    @property
    def port(self):
        """Returns server port"""
        return self.env['SERVER_PORT']

    @property
    def location(self):
        """Returns the scripts virtual location"""
        return self.env.get('SCRIPT_NAME', '')

    @property
    def method(self):
        """Returns the request method"""
        return self.env['REQUEST_METHOD']

    @property
    def remote_addr(self):
        if 'HTTP_X_FORWARDED_FOR' in self.env:
            return self.env['HTTP_X_FORWARDED_FOR'].split(',')[-1].strip()
        else:
            return self.env['REMOTE_ADDR']

    def add_response_callback(self, function):
        self.resp_callbacks.append(function)
