from functools import wraps
from mako.lookup import TemplateLookup
from distill import PY2
import json
from distill.exceptions import HTTPInternalServerError
from distill.response import Response


class RenderFactory(object):
    """
    This class provides a wrapper for handling rendering operations

    """
    _factory = None

    def __init__(self, settings):
        """ Init
         Args:
            settings: The application's settings dict
        """
        if PY2:  # pragma: no cover
            self._template_lookup = TemplateLookup(output_encoding='ascii')
        else:  # pragma: no cover
            self._template_lookup = TemplateLookup(input_encoding='utf-8')
        self._template_lookup.directories.append(settings.get('distill.document_root', ''))
        self._template_lookup.module_directory = settings.get('distill.document_root', '')
        self._renderers = {}

    def __call__(self, template, data, request, response, **rkwargs):
        """ Actually render the response

        Notes:
            The current request will be available to template
            template as req

        Args:
            template: The template you're looking up
            data: The data to be passed to the template
            request: Current request
            response: Current response
        """

        if '.mako' == template.lower()[-5:]:
            if type(data) != dict:
                return data

            response.headers['Content-Type'] = 'text/html'
            data['req'] = request
            return self._template_lookup.get_template(template).render(**data)
        elif template in self._renderers:
            return self._renderers[template](data, request, response, **rkwargs)
        raise HTTPInternalServerError(description="Missing template file {0}".format(template))

    def register_renderer(self, name, serializer):
        """Adds template to the current instances renderers dict"""
        self._renderers[name] = serializer

    @staticmethod
    def create(settings):
        """Initializes the RenderFactory"""
        RenderFactory._factory = RenderFactory(settings)
        RenderFactory._factory.register_renderer('json', JSON())

    @staticmethod
    def render(template, data, request, response, **rkwargs):
        """Returns the rendered response to a template"""
        return RenderFactory._factory(template, data, request, response, **rkwargs)

    @staticmethod
    def add_renderer(name, serializer):
        """Adds a template to the RenderFactory"""
        RenderFactory._factory.register_renderer(name, serializer)


def renderer(template, **rkwargs):
    """ Decorator for rendering responses

    Notes:
        When using this decorator the returned value of
        on_get or on_post is treated as arguments passed
        to the template, as such their meaning will vary
        accordingly
    """
    def _render(method):
        @wraps(method)
        def _call(*args, **kwargs):
            data = method(*args, **kwargs)
            if isinstance(data, Response):
                return data
            if len(args) == 2:
                return RenderFactory.render(template, data, *args, **rkwargs)
            else:
                return RenderFactory.render(template, data, args[1], args[2], **rkwargs)
        return _call
    return _render


class JSON(object):
    def __init__(self, serializer=json.dumps, **kwargs):
        """ Init
         Args:
            serializer: The serialzer to be used to stringify the object
            kwargs: All kwargs will be passed to the serializer
        """
        self.serializer = serializer
        self.kw = kwargs

    def __call__(self, data, request, response, pad=False):
        """ Render the response to the template

        Notes:
            Templates should be callables that accept the
            following arguments and return either a string
            representing the rendered response body, or a
            new response

        Args:
            data: The data to be rendered
            request: The current request, to be used as needed
            response: The current response

        """
        response.headers['Content-Type'] = 'application/json'

        def default(obj):
            if hasattr(obj, 'json'):
                return obj.json(request)
            else:
                raise TypeError('%r is not JSON serializable' % obj)
        if pad:
            return ")]}',\n" + self.serializer(data, default=default, **self.kw)
        return self.serializer(data, default=default, **self.kw)