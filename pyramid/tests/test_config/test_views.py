import unittest
from pyramid import testing

from pyramid.tests.test_config import IDummy

from pyramid.tests.test_config import dummy_view

from pyramid.exceptions import ConfigurationError
from pyramid.exceptions import ConfigurationExecutionError
from pyramid.exceptions import ConfigurationConflictError

class TestViewsConfigurationMixin(unittest.TestCase):
    def _makeOne(self, *arg, **kw):
        from pyramid.config import Configurator
        config = Configurator(*arg, **kw)
        return config

    def _getViewCallable(self, config, ctx_iface=None, request_iface=None,
                         name='', exception_view=False):
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IExceptionViewClassifier
        if exception_view:
            classifier = IExceptionViewClassifier
        else:
            classifier = IViewClassifier
        if ctx_iface is None:
            ctx_iface = Interface
        if request_iface is None:
            request_iface = IRequest
        return config.registry.adapters.lookup(
            (classifier, request_iface, ctx_iface), IView, name=name,
            default=None)

    def _registerRenderer(self, config, name='.txt'):
        from pyramid.interfaces import IRendererFactory
        from pyramid.interfaces import ITemplateRenderer
        from zope.interface import implementer
        @implementer(ITemplateRenderer)
        class Renderer:
            def __init__(self, info):
                self.__class__.info = info
            def __call__(self, *arg):
                return 'Hello!'
        config.registry.registerUtility(Renderer, IRendererFactory, name=name)
        return Renderer

    def _makeRequest(self, config):
        request = DummyRequest()
        request.registry = config.registry
        return request

    def _assertNotFound(self, wrapper, *arg):
        from pyramid.httpexceptions import HTTPNotFound
        self.assertRaises(HTTPNotFound, wrapper, *arg)

    def _getRouteRequestIface(self, config, name):
        from pyramid.interfaces import IRouteRequest
        iface = config.registry.getUtility(IRouteRequest, name)
        return iface

    def _assertRoute(self, config, name, path, num_predicates=0):
        from pyramid.interfaces import IRoutesMapper
        mapper = config.registry.getUtility(IRoutesMapper)
        routes = mapper.get_routes()
        route = routes[0]
        self.assertEqual(len(routes), 1)
        self.assertEqual(route.name, name)
        self.assertEqual(route.path, path)
        self.assertEqual(len(routes[0].predicates), num_predicates)
        return route

    def test_add_view_view_callable_None_no_renderer(self):
        config = self._makeOne(autocommit=True)
        self.assertRaises(ConfigurationError, config.add_view)

    def test_add_view_with_request_type_and_route_name(self):
        config = self._makeOne(autocommit=True)
        view = lambda *arg: 'OK'
        self.assertRaises(ConfigurationError, config.add_view, view, '', None,
                          None, True, True)

    def test_add_view_with_request_type(self):
        from pyramid.renderers import null_renderer
        from zope.interface import directlyProvides
        from pyramid.interfaces import IRequest
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view,
                        request_type='pyramid.interfaces.IRequest',
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = DummyRequest()
        self._assertNotFound(wrapper, None, request)
        directlyProvides(request, IRequest)
        result = wrapper(None, request)
        self.assertEqual(result, 'OK')

    def test_add_view_view_callable_None_with_renderer(self):
        config = self._makeOne(autocommit=True)
        self._registerRenderer(config, name='dummy')
        config.add_view(renderer='dummy')
        view = self._getViewCallable(config)
        self.assertTrue(b'Hello!' in view(None, None).body)

    def test_add_view_wrapped_view_is_decorated(self):
        def view(request): # request-only wrapper
            """ """
        config = self._makeOne(autocommit=True)
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        self.assertEqual(wrapper.__module__, view.__module__)
        self.assertEqual(wrapper.__name__, view.__name__)
        self.assertEqual(wrapper.__doc__, view.__doc__)

    def test_add_view_view_callable_dottedname(self):
        from pyramid.renderers import null_renderer
        config = self._makeOne(autocommit=True)
        config.add_view(view='pyramid.tests.test_config.dummy_view',
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_with_function_callable(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_with_function_callable_requestonly(self):
        from pyramid.renderers import null_renderer
        def view(request):
            return 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_with_decorator(self):
        from pyramid.renderers import null_renderer
        def view(request):
            """ ABC """
            return 'OK'
        def view_wrapper(fn):
            def inner(context, request):
                return fn(context, request)
            return inner
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, decorator=view_wrapper,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertFalse(wrapper is view)
        self.assertEqual(wrapper.__doc__, view.__doc__)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_with_http_cache(self):
        import datetime
        from pyramid.response import Response
        response = Response('OK')
        def view(request):
            """ ABC """
            return response
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, http_cache=(86400, {'public':True}))
        wrapper = self._getViewCallable(config)
        self.assertFalse(wrapper is view)
        self.assertEqual(wrapper.__doc__, view.__doc__)
        request = testing.DummyRequest()
        when = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        result = wrapper(None, request)
        self.assertEqual(result, response)
        headers = dict(response.headerlist)
        self.assertEqual(headers['Cache-Control'], 'max-age=86400, public')
        expires = parse_httpdate(headers['Expires'])
        assert_similar_datetime(expires, when)

    def test_add_view_as_instance(self):
        from pyramid.renderers import null_renderer
        class AView:
            def __call__(self, context, request):
                """ """
                return 'OK'
        view = AView()
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_as_instance_requestonly(self):
        from pyramid.renderers import null_renderer
        class AView:
            def __call__(self, request):
                """ """
                return 'OK'
        view = AView()
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_as_oldstyle_class(self):
        from pyramid.renderers import null_renderer
        class view:
            def __init__(self, context, request):
                self.context = context
                self.request = request

            def __call__(self):
                return 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result, 'OK')
        self.assertEqual(request.__view__.__class__, view)

    def test_add_view_as_oldstyle_class_requestonly(self):
        from pyramid.renderers import null_renderer
        class view:
            def __init__(self, request):
                self.request = request

            def __call__(self):
                return 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)

        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result, 'OK')
        self.assertEqual(request.__view__.__class__, view)

    def test_add_view_context_as_class(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        view = lambda *arg: 'OK'
        class Foo:
            pass
        config = self._makeOne(autocommit=True)
        config.add_view(context=Foo, view=view, renderer=null_renderer)
        foo = implementedBy(Foo)
        wrapper = self._getViewCallable(config, foo)
        self.assertEqual(wrapper, view)

    def test_add_view_context_as_iface(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(context=IDummy, view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config, IDummy)
        self.assertEqual(wrapper, view)

    def test_add_view_context_as_dottedname(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(context='pyramid.tests.test_config.IDummy',
                        view=view,  renderer=null_renderer)
        wrapper = self._getViewCallable(config, IDummy)
        self.assertEqual(wrapper, view)

    def test_add_view_for__as_dottedname(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(for_='pyramid.tests.test_config.IDummy',
                        view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config, IDummy)
        self.assertEqual(wrapper, view)

    def test_add_view_for_as_class(self):
        # ``for_`` is older spelling for ``context``
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        view = lambda *arg: 'OK'
        class Foo:
            pass
        config = self._makeOne(autocommit=True)
        config.add_view(for_=Foo, view=view, renderer=null_renderer)
        foo = implementedBy(Foo)
        wrapper = self._getViewCallable(config, foo)
        self.assertEqual(wrapper, view)

    def test_add_view_for_as_iface(self):
        # ``for_`` is older spelling for ``context``
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(for_=IDummy, view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config, IDummy)
        self.assertEqual(wrapper, view)

    def test_add_view_context_trumps_for(self):
        # ``for_`` is older spelling for ``context``
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        class Foo:
            pass
        config.add_view(context=IDummy, for_=Foo, view=view,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config, IDummy)
        self.assertEqual(wrapper, view)

    def test_add_view_register_secured_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import ISecuredView
        from pyramid.interfaces import IViewClassifier
        view = lambda *arg: 'OK'
        view.__call_permissive__ = view
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, renderer=null_renderer)
        wrapper = config.registry.adapters.lookup(
            (IViewClassifier, IRequest, Interface),
            ISecuredView, name='', default=None)
        self.assertEqual(wrapper, view)

    def test_add_view_exception_register_secured_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IExceptionViewClassifier
        view = lambda *arg: 'OK'
        view.__call_permissive__ = view
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, context=RuntimeError, renderer=null_renderer)
        wrapper = config.registry.adapters.lookup(
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='', default=None)
        self.assertEqual(wrapper, view)

    def test_add_view_same_phash_overrides_existing_single_view(self):
        from pyramid.renderers import null_renderer
        from hashlib import md5
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IMultiView
        phash = md5()
        phash.update('xhr:True')
        view = lambda *arg: 'NOT OK'
        view.__phash__ = phash.hexdigest()
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface), IView, name='')
        def newview(context, request):
            return 'OK'
        config.add_view(view=newview, xhr=True, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertFalse(IMultiView.providedBy(wrapper))
        request = DummyRequest()
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_exc_same_phash_overrides_existing_single_view(self):
        from pyramid.renderers import null_renderer
        from hashlib import md5
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IExceptionViewClassifier
        from pyramid.interfaces import IMultiView
        phash = md5()
        phash.update('xhr:True')
        view = lambda *arg: 'NOT OK'
        view.__phash__ = phash.hexdigest()
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        def newview(context, request):
            return 'OK'
        config.add_view(view=newview, xhr=True, context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertFalse(IMultiView.providedBy(wrapper))
        request = DummyRequest()
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_default_phash_overrides_no_phash(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IMultiView
        view = lambda *arg: 'NOT OK'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface), IView, name='')
        def newview(context, request):
            return 'OK'
        config.add_view(view=newview, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertFalse(IMultiView.providedBy(wrapper))
        request = DummyRequest()
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_exc_default_phash_overrides_no_phash(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IExceptionViewClassifier
        from pyramid.interfaces import IMultiView
        view = lambda *arg: 'NOT OK'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        def newview(context, request):
            return 'OK'
        config.add_view(view=newview, context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertFalse(IMultiView.providedBy(wrapper))
        request = DummyRequest()
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_default_phash_overrides_default_phash(self):
        from pyramid.renderers import null_renderer
        from pyramid.config.util import DEFAULT_PHASH
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IMultiView
        view = lambda *arg: 'NOT OK'
        view.__phash__ = DEFAULT_PHASH
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface), IView, name='')
        def newview(context, request):
            return 'OK'
        config.add_view(view=newview, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertFalse(IMultiView.providedBy(wrapper))
        request = DummyRequest()
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_exc_default_phash_overrides_default_phash(self):
        from pyramid.renderers import null_renderer
        from pyramid.config.util import DEFAULT_PHASH
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IExceptionViewClassifier
        from pyramid.interfaces import IMultiView
        view = lambda *arg: 'NOT OK'
        view.__phash__ = DEFAULT_PHASH
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        def newview(context, request):
            return 'OK'
        config.add_view(view=newview, context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertFalse(IMultiView.providedBy(wrapper))
        request = DummyRequest()
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_multiview_replaces_existing_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IMultiView
        view = lambda *arg: 'OK'
        view.__phash__ = 'abc'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface), IView, name='')
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_exc_multiview_replaces_existing_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IExceptionViewClassifier
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IMultiView
        view = lambda *arg: 'OK'
        view.__phash__ = 'abc'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        config.add_view(view=view, context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_multiview_replaces_existing_securedview(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import ISecuredView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        view = lambda *arg: 'OK'
        view.__phash__ = 'abc'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface),
            ISecuredView, name='')
        config.add_view(view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_exc_multiview_replaces_existing_securedview(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import ISecuredView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IExceptionViewClassifier
        view = lambda *arg: 'OK'
        view.__phash__ = 'abc'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IViewClassifier, IRequest, implementedBy(RuntimeError)),
            ISecuredView, name='')
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            ISecuredView, name='')
        config.add_view(view=view, context=RuntimeError, renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_with_accept_multiview_replaces_existing_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        def view(context, request):
            return 'OK'
        def view2(context, request):
            return 'OK2'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface), IView, name='')
        config.add_view(view=view2, accept='text/html', renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(len(wrapper.views), 1)
        self.assertEqual(len(wrapper.media_views), 1)
        self.assertEqual(wrapper(None, None), 'OK')
        request = DummyRequest()
        request.accept = DummyAccept('text/html', 'text/html')
        self.assertEqual(wrapper(None, request), 'OK2')

    def test_add_view_exc_with_accept_multiview_replaces_existing_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IExceptionViewClassifier
        def view(context, request):
            return 'OK'
        def view2(context, request):
            return 'OK2'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        config.add_view(view=view2, accept='text/html', context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(len(wrapper.views), 1)
        self.assertEqual(len(wrapper.media_views), 1)
        self.assertEqual(wrapper(None, None), 'OK')
        request = DummyRequest()
        request.accept = DummyAccept('text/html', 'text/html')
        self.assertEqual(wrapper(None, request), 'OK2')

    def test_add_view_multiview_replaces_existing_view_with___accept__(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        def view(context, request):
            return 'OK'
        def view2(context, request):
            return 'OK2'
        view.__accept__ = 'text/html'
        view.__phash__ = 'abc'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface), IView, name='')
        config.add_view(view=view2, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(len(wrapper.views), 1)
        self.assertEqual(len(wrapper.media_views), 1)
        self.assertEqual(wrapper(None, None), 'OK2')
        request = DummyRequest()
        request.accept = DummyAccept('text/html')
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_exc_mulview_replaces_existing_view_with___accept__(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IExceptionViewClassifier
        def view(context, request):
            return 'OK'
        def view2(context, request):
            return 'OK2'
        view.__accept__ = 'text/html'
        view.__phash__ = 'abc'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IView, name='')
        config.add_view(view=view2, context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual(len(wrapper.views), 1)
        self.assertEqual(len(wrapper.media_views), 1)
        self.assertEqual(wrapper(None, None), 'OK2')
        request = DummyRequest()
        request.accept = DummyAccept('text/html')
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_multiview_replaces_multiview(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        view = DummyMultiView()
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Interface),
            IMultiView, name='')
        view2 = lambda *arg: 'OK2'
        config.add_view(view=view2, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual([x[:2] for x in wrapper.views], [(view2, None)])
        self.assertEqual(wrapper(None, None), 'OK1')

    def test_add_view_exc_multiview_replaces_multiview(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IExceptionViewClassifier
        view = DummyMultiView()
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view,
            (IViewClassifier, IRequest, implementedBy(RuntimeError)),
            IMultiView, name='')
        config.registry.registerAdapter(
            view,
            (IExceptionViewClassifier, IRequest, implementedBy(RuntimeError)),
            IMultiView, name='')
        view2 = lambda *arg: 'OK2'
        config.add_view(view=view2, context=RuntimeError,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError), exception_view=True)
        self.assertTrue(IMultiView.providedBy(wrapper))
        self.assertEqual([x[:2] for x in wrapper.views], [(view2, None)])
        self.assertEqual(wrapper(None, None), 'OK1')

    def test_add_view_multiview_context_superclass_then_subclass(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        class ISuper(Interface):
            pass
        class ISub(ISuper):
            pass
        view = lambda *arg: 'OK'
        view2 = lambda *arg: 'OK2'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, ISuper), IView, name='')
        config.add_view(view=view2, for_=ISub, renderer=null_renderer)
        wrapper = self._getViewCallable(config, ISuper, IRequest)
        self.assertFalse(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK')
        wrapper = self._getViewCallable(config, ISub, IRequest)
        self.assertFalse(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK2')

    def test_add_view_multiview_exception_superclass_then_subclass(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.interfaces import IView
        from pyramid.interfaces import IMultiView
        from pyramid.interfaces import IViewClassifier
        from pyramid.interfaces import IExceptionViewClassifier
        class Super(Exception):
            pass
        class Sub(Super):
            pass
        view = lambda *arg: 'OK'
        view2 = lambda *arg: 'OK2'
        config = self._makeOne(autocommit=True)
        config.registry.registerAdapter(
            view, (IViewClassifier, IRequest, Super), IView, name='')
        config.registry.registerAdapter(
            view, (IExceptionViewClassifier, IRequest, Super), IView, name='')
        config.add_view(view=view2, for_=Sub, renderer=null_renderer)
        wrapper = self._getViewCallable(
            config, implementedBy(Super), IRequest)
        wrapper_exc_view = self._getViewCallable(
            config, implementedBy(Super), IRequest, exception_view=True)
        self.assertEqual(wrapper_exc_view, wrapper)
        self.assertFalse(IMultiView.providedBy(wrapper_exc_view))
        self.assertEqual(wrapper_exc_view(None, None), 'OK')
        wrapper = self._getViewCallable(
            config, implementedBy(Sub), IRequest)
        wrapper_exc_view = self._getViewCallable(
            config, implementedBy(Sub), IRequest, exception_view=True)
        self.assertEqual(wrapper_exc_view, wrapper)
        self.assertFalse(IMultiView.providedBy(wrapper_exc_view))
        self.assertEqual(wrapper_exc_view(None, None), 'OK2')

    def test_add_view_multiview_call_ordering(self):
        from pyramid.renderers import null_renderer as nr
        from zope.interface import directlyProvides
        def view1(context, request): return 'view1'
        def view2(context, request): return 'view2'
        def view3(context, request): return 'view3'
        def view4(context, request): return 'view4'
        def view5(context, request): return 'view5'
        def view6(context, request): return 'view6'
        def view7(context, request): return 'view7'
        def view8(context, request): return 'view8'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view1, renderer=nr)
        config.add_view(view=view2, request_method='POST', renderer=nr)
        config.add_view(view=view3,request_param='param', renderer=nr)
        config.add_view(view=view4, containment=IDummy, renderer=nr)
        config.add_view(view=view5, request_method='POST',
                        request_param='param',  renderer=nr)
        config.add_view(view=view6, request_method='POST', containment=IDummy,
                        renderer=nr)
        config.add_view(view=view7, request_param='param', containment=IDummy,
                        renderer=nr)
        config.add_view(view=view8, request_method='POST',request_param='param',
                        containment=IDummy, renderer=nr)


        wrapper = self._getViewCallable(config)

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.method = 'GET'
        request.params = {}
        self.assertEqual(wrapper(ctx, request), 'view1')

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.params = {}
        request.method = 'POST'
        self.assertEqual(wrapper(ctx, request), 'view2')

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.params = {'param':'1'}
        request.method = 'GET'
        self.assertEqual(wrapper(ctx, request), 'view3')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.method = 'GET'
        request.params = {}
        self.assertEqual(wrapper(ctx, request), 'view4')

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.method = 'POST'
        request.params = {'param':'1'}
        self.assertEqual(wrapper(ctx, request), 'view5')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.params = {}
        request.method = 'POST'
        self.assertEqual(wrapper(ctx, request), 'view6')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.method = 'GET'
        request.params = {'param':'1'}
        self.assertEqual(wrapper(ctx, request), 'view7')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.method = 'POST'
        request.params = {'param':'1'}
        self.assertEqual(wrapper(ctx, request), 'view8')

    def test_add_view_with_template_renderer(self):
        from pyramid.tests import test_config
        from pyramid.interfaces import ISettings
        class view(object):
            def __init__(self, context, request):
                self.request = request
                self.context = context

            def __call__(self):
                return {'a':'1'}
        config = self._makeOne(autocommit=True)
        renderer = self._registerRenderer(config)
        fixture = 'pyramid.tests.test_config:files/minimal.txt'
        config.add_view(view=view, renderer=fixture)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result.body, b'Hello!')
        settings = config.registry.queryUtility(ISettings)
        result = renderer.info
        self.assertEqual(result.registry, config.registry)
        self.assertEqual(result.type, '.txt')
        self.assertEqual(result.package, test_config)
        self.assertEqual(result.name, fixture)
        self.assertEqual(result.settings, settings)

    def test_add_view_with_default_renderer(self):
        class view(object):
            def __init__(self, context, request):
                self.request = request
                self.context = context

            def __call__(self):
                return {'a':'1'}
        config = self._makeOne(autocommit=True)
        class moo(object):
            def __init__(self, *arg, **kw):
                pass
            def __call__(self, *arg, **kw):
                return 'moo'
        config.add_renderer(None, moo)
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result.body, b'moo')

    def test_add_view_with_template_renderer_no_callable(self):
        from pyramid.tests import test_config
        from pyramid.interfaces import ISettings
        config = self._makeOne(autocommit=True)
        renderer = self._registerRenderer(config)
        fixture = 'pyramid.tests.test_config:files/minimal.txt'
        config.add_view(view=None, renderer=fixture)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result.body, b'Hello!')
        settings = config.registry.queryUtility(ISettings)
        result = renderer.info
        self.assertEqual(result.registry, config.registry)
        self.assertEqual(result.type, '.txt')
        self.assertEqual(result.package, test_config)
        self.assertEqual(result.name, fixture)
        self.assertEqual(result.settings, settings)

    def test_add_view_with_request_type_as_iface(self):
        from pyramid.renderers import null_renderer
        from zope.interface import directlyProvides
        def view(context, request):
            return 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(request_type=IDummy, view=view, renderer=null_renderer)
        wrapper = self._getViewCallable(config, None)
        request = self._makeRequest(config)
        directlyProvides(request, IDummy)
        result = wrapper(None, request)
        self.assertEqual(result, 'OK')

    def test_add_view_with_request_type_as_noniface(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self.assertRaises(ConfigurationError,
                          config.add_view, view, '', None, None, object)

    def test_add_view_with_route_name(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_route('foo', '/a/b')
        config.add_view(view=view, route_name='foo', renderer=null_renderer)
        request_iface = self._getRouteRequestIface(config, 'foo')
        self.assertNotEqual(request_iface, None)
        wrapper = self._getViewCallable(config, request_iface=request_iface)
        self.assertNotEqual(wrapper, None)
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_with_nonexistant_route_name(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, route_name='foo', renderer=null_renderer)
        self.assertRaises(ConfigurationExecutionError, config.commit)

    def test_add_view_with_route_name_exception(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_route('foo', '/a/b')
        config.add_view(view=view, route_name='foo', context=RuntimeError,
                        renderer=null_renderer)
        request_iface = self._getRouteRequestIface(config, 'foo')
        wrapper_exc_view = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError),
            request_iface=request_iface, exception_view=True)
        self.assertNotEqual(wrapper_exc_view, None)
        wrapper = self._getViewCallable(
            config, ctx_iface=implementedBy(RuntimeError),
            request_iface=request_iface)
        self.assertEqual(wrapper_exc_view, wrapper)
        self.assertEqual(wrapper_exc_view(None, None), 'OK')

    def test_add_view_with_request_method_true(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_method='POST',
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'POST'
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_method_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_method='POST')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'GET'
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_request_method_sequence_true(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_method=('POST', 'GET'),
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'POST'
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_method_sequence_conflict(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_method=('POST', 'GET'),
                        renderer=null_renderer)
        config.add_view(view=view, request_method=('GET', 'POST'),
                        renderer=null_renderer)
        self.assertRaises(ConfigurationConflictError, config.commit)

    def test_add_view_with_request_method_sequence_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_method=('POST', 'HEAD'))
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'GET'
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_request_param_noval_true(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_param='abc', renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {'abc':''}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_param_noval_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_param='abc')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_request_param_val_true(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_param='abc=123',
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {'abc':'123'}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_param_val_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_param='abc=123')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {'abc':''}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_xhr_true(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, xhr=True, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_xhr_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, xhr=True)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.is_xhr = False
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_header_badregex(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self.assertRaises(ConfigurationError,
                          config.add_view, view=view, header='Host:a\\')

    def test_add_view_with_header_noval_match(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, header='Host', renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'Host':'whatever'}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_header_noval_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, header='Host')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'NotHost':'whatever'}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_header_val_match(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, header=r'Host:\d', renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'Host':'1'}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_header_val_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, header=r'Host:\d')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'Host':'abc'}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_header_val_missing(self):
        from pyramid.httpexceptions import HTTPNotFound
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, header=r'Host:\d')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'NoHost':'1'}
        self.assertRaises(HTTPNotFound, wrapper, None, request)

    def test_add_view_with_accept_match(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, accept='text/xml', renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.accept = ['text/xml']
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_accept_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, accept='text/xml')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.accept = ['text/html']
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_containment_true(self):
        from pyramid.renderers import null_renderer
        from zope.interface import directlyProvides
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, containment=IDummy, renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        context = DummyContext()
        directlyProvides(context, IDummy)
        self.assertEqual(wrapper(context, None), 'OK')

    def test_add_view_with_containment_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, containment=IDummy)
        wrapper = self._getViewCallable(config)
        context = DummyContext()
        self._assertNotFound(wrapper, context, None)

    def test_add_view_with_containment_dottedname(self):
        from pyramid.renderers import null_renderer
        from zope.interface import directlyProvides
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(
            view=view,
            containment='pyramid.tests.test_config.IDummy',
            renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        context = DummyContext()
        directlyProvides(context, IDummy)
        self.assertEqual(wrapper(context, None), 'OK')

    def test_add_view_with_path_info_badregex(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self.assertRaises(ConfigurationError,
                          config.add_view, view=view, path_info='\\')

    def test_add_view_with_path_info_match(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, path_info='/foo', renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.path_info = '/foo'
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_path_info_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, path_info='/foo')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.path_info = '/'
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_custom_predicates_match(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        def pred1(context, request):
            return True
        def pred2(context, request):
            return True
        predicates = (pred1, pred2)
        config.add_view(view=view, custom_predicates=predicates,
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_custom_predicates_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne(autocommit=True)
        def pred1(context, request):
            return True
        def pred2(context, request):
            return False
        predicates = (pred1, pred2)
        config.add_view(view=view, custom_predicates=predicates)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        self._assertNotFound(wrapper, None, request)

    def test_add_view_custom_predicate_bests_standard_predicate(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        view2 = lambda *arg: 'NOT OK'
        config = self._makeOne(autocommit=True)
        def pred1(context, request):
            return True
        config.add_view(view=view, custom_predicates=(pred1,),
                        renderer=null_renderer)
        config.add_view(view=view2, request_method='GET',
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'GET'
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_custom_more_preds_first_bests_fewer_preds_last(self):
        from pyramid.renderers import null_renderer
        view = lambda *arg: 'OK'
        view2 = lambda *arg: 'NOT OK'
        config = self._makeOne(autocommit=True)
        config.add_view(view=view, request_method='GET', xhr=True,
                        renderer=null_renderer)
        config.add_view(view=view2, request_method='GET',
                        renderer=null_renderer)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'GET'
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_same_predicates(self):
        view2 = lambda *arg: 'second'
        view1 = lambda *arg: 'first'
        config = self._makeOne()
        config.add_view(view=view1)
        config.add_view(view=view2)
        self.assertRaises(ConfigurationConflictError, config.commit)

    def test_add_view_with_permission(self):
        from pyramid.renderers import null_renderer
        view1 = lambda *arg: 'OK'
        outerself = self
        class DummyPolicy(object):
            def effective_principals(self, r):
                outerself.assertEqual(r, request)
                return ['abc']
            def permits(self, context, principals, permission):
                outerself.assertEqual(context, None)
                outerself.assertEqual(principals, ['abc'])
                outerself.assertEqual(permission, 'view')
                return True
        policy = DummyPolicy()
        config = self._makeOne(authorization_policy=policy,
                               authentication_policy=policy,
                               autocommit=True)
        config.add_view(view=view1, permission='view', renderer=null_renderer)
        view = self._getViewCallable(config)
        request = self._makeRequest(config)
        self.assertEqual(view(None, request), 'OK')

    def test_add_view_with_default_permission_no_explicit_permission(self):
        from pyramid.renderers import null_renderer
        view1 = lambda *arg: 'OK'
        outerself = self
        class DummyPolicy(object):
            def effective_principals(self, r):
                outerself.assertEqual(r, request)
                return ['abc']
            def permits(self, context, principals, permission):
                outerself.assertEqual(context, None)
                outerself.assertEqual(principals, ['abc'])
                outerself.assertEqual(permission, 'view')
                return True
        policy = DummyPolicy()
        config = self._makeOne(authorization_policy=policy,
                               authentication_policy=policy,
                               default_permission='view',
                               autocommit=True)
        config.add_view(view=view1, renderer=null_renderer)
        view = self._getViewCallable(config)
        request = self._makeRequest(config)
        self.assertEqual(view(None, request), 'OK')

    def test_add_view_with_no_default_permission_no_explicit_permission(self):
        from pyramid.renderers import null_renderer
        view1 = lambda *arg: 'OK'
        class DummyPolicy(object): pass # wont be called
        policy = DummyPolicy()
        config = self._makeOne(authorization_policy=policy,
                               authentication_policy=policy,
                               autocommit=True)
        config.add_view(view=view1, renderer=null_renderer)
        view = self._getViewCallable(config)
        request = self._makeRequest(config)
        self.assertEqual(view(None, request), 'OK')

    def test_derive_view_function(self):
        from pyramid.renderers import null_renderer
        def view(request):
            return 'OK'
        config = self._makeOne()
        result = config.derive_view(view, renderer=null_renderer)
        self.assertFalse(result is view)
        self.assertEqual(result(None, None), 'OK')

    def test_derive_view_dottedname(self):
        from pyramid.renderers import null_renderer
        config = self._makeOne()
        result = config.derive_view(
            'pyramid.tests.test_config.dummy_view',
            renderer=null_renderer)
        self.assertFalse(result is dummy_view)
        self.assertEqual(result(None, None), 'OK')

    def test_derive_view_with_default_renderer_no_explicit_renderer(self):
        config = self._makeOne()
        class moo(object):
            def __init__(self, view):
                pass
            def __call__(self, *arg, **kw):
                return 'moo'
        config.add_renderer(None, moo)
        config.commit()
        def view(request):
            return 'OK'
        result = config.derive_view(view)
        self.assertFalse(result is view)
        self.assertEqual(result(None, None).body, b'moo')

    def test_derive_view_with_default_renderer_with_explicit_renderer(self):
        class moo(object): pass
        class foo(object):
            def __init__(self, view):
                pass
            def __call__(self, *arg, **kw):
                return 'foo'
        def view(request):
            return 'OK'
        config = self._makeOne()
        config.add_renderer(None, moo)
        config.add_renderer('foo', foo)
        config.commit()
        result = config.derive_view(view, renderer='foo')
        self.assertFalse(result is view)
        request = self._makeRequest(config)
        self.assertEqual(result(None, request).body, b'foo')

    def test_add_static_view_here_no_utility_registered(self):
        from pyramid.renderers import null_renderer
        from zope.interface import Interface
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        config = self._makeOne(autocommit=True)
        config.add_static_view('static', 'files', renderer=null_renderer)
        request_type = self._getRouteRequestIface(config, '__static/')
        self._assertRoute(config, '__static/', 'static/*subpath')
        wrapped = config.registry.adapters.lookup(
            (IViewClassifier, request_type, Interface), IView, name='')
        from pyramid.request import Request
        request = Request.blank('/static/minimal.pt')
        request.subpath = ('minimal.pt', )
        result = wrapped(None, request)
        self.assertEqual(result.status, '200 OK')

    def test_add_static_view_package_relative(self):
        from pyramid.interfaces import IStaticURLInfo
        info = DummyStaticURLInfo()
        config = self._makeOne(autocommit=True)
        config.registry.registerUtility(info, IStaticURLInfo)
        config.add_static_view('static',
                               'pyramid.tests.test_config:files')
        self.assertEqual(
            info.added,
            [(config, 'static', 'pyramid.tests.test_config:files', {})])

    def test_add_static_view_package_here_relative(self):
        from pyramid.interfaces import IStaticURLInfo
        info = DummyStaticURLInfo()
        config = self._makeOne(autocommit=True)
        config.registry.registerUtility(info, IStaticURLInfo)
        config.add_static_view('static', 'files')
        self.assertEqual(
            info.added,
            [(config, 'static', 'pyramid.tests.test_config:files', {})])

    def test_add_static_view_absolute(self):
        import os
        from pyramid.interfaces import IStaticURLInfo
        info = DummyStaticURLInfo()
        config = self._makeOne(autocommit=True)
        config.registry.registerUtility(info, IStaticURLInfo)
        here = os.path.dirname(__file__)
        static_path = os.path.join(here, 'files')
        config.add_static_view('static', static_path)
        self.assertEqual(info.added,
                         [(config, 'static', static_path, {})])
    
    def test_set_forbidden_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.httpexceptions import HTTPForbidden
        config = self._makeOne(autocommit=True)
        view = lambda *arg: 'OK'
        config.set_forbidden_view(view, renderer=null_renderer)
        request = self._makeRequest(config)
        view = self._getViewCallable(config,
                                     ctx_iface=implementedBy(HTTPForbidden),
                                     request_iface=IRequest)
        result = view(None, request)
        self.assertEqual(result, 'OK')

    def test_set_forbidden_view_request_has_context(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.httpexceptions import HTTPForbidden
        config = self._makeOne(autocommit=True)
        view = lambda *arg: arg
        config.set_forbidden_view(view, renderer=null_renderer)
        request = self._makeRequest(config)
        request.context = 'abc'
        view = self._getViewCallable(config,
                                     ctx_iface=implementedBy(HTTPForbidden),
                                     request_iface=IRequest)
        result = view(None, request)
        self.assertEqual(result, ('abc', request))



    def test_set_notfound_view(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.httpexceptions import HTTPNotFound
        config = self._makeOne(autocommit=True)
        view = lambda *arg: arg
        config.set_notfound_view(view, renderer=null_renderer)
        request = self._makeRequest(config)
        view = self._getViewCallable(config,
                                     ctx_iface=implementedBy(HTTPNotFound),
                                     request_iface=IRequest)
        result = view(None, request)
        self.assertEqual(result, (None, request))

    def test_set_notfound_view_request_has_context(self):
        from pyramid.renderers import null_renderer
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.httpexceptions import HTTPNotFound
        config = self._makeOne(autocommit=True)
        view = lambda *arg: arg
        config.set_notfound_view(view, renderer=null_renderer)
        request = self._makeRequest(config)
        request.context = 'abc'
        view = self._getViewCallable(config,
                                     ctx_iface=implementedBy(HTTPNotFound),
                                     request_iface=IRequest)
        result = view(None, request)
        self.assertEqual(result, ('abc', request))

    @testing.skip_on('java')
    def test_set_notfound_view_with_renderer(self):
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.httpexceptions import HTTPNotFound
        config = self._makeOne(autocommit=True)
        view = lambda *arg: {}
        config.set_notfound_view(
            view,
            renderer='pyramid.tests.test_config:files/minimal.pt')
        config.begin()
        try: # chameleon depends on being able to find a threadlocal registry
            request = self._makeRequest(config)
            view = self._getViewCallable(config,
                                         ctx_iface=implementedBy(HTTPNotFound),
                                         request_iface=IRequest)
            result = view(None, request)
        finally:
            config.end()
        self.assertTrue(b'div' in result.body)

    @testing.skip_on('java')
    def test_set_forbidden_view_with_renderer(self):
        from zope.interface import implementedBy
        from pyramid.interfaces import IRequest
        from pyramid.httpexceptions import HTTPForbidden
        config = self._makeOne(autocommit=True)
        view = lambda *arg: {}
        config.set_forbidden_view(
            view,
            renderer='pyramid.tests.test_config:files/minimal.pt')
        config.begin()
        try: # chameleon requires a threadlocal registry
            request = self._makeRequest(config)
            view = self._getViewCallable(config,
                                         ctx_iface=implementedBy(HTTPForbidden),
                                         request_iface=IRequest)
            result = view(None, request)
        finally:
            config.end()
        self.assertTrue(b'div' in result.body)

    def test_set_view_mapper(self):
        from pyramid.interfaces import IViewMapperFactory
        config = self._makeOne(autocommit=True)
        mapper = object()
        config.set_view_mapper(mapper)
        result = config.registry.getUtility(IViewMapperFactory)
        self.assertEqual(result, mapper)

    def test_set_view_mapper_dottedname(self):
        from pyramid.interfaces import IViewMapperFactory
        config = self._makeOne(autocommit=True)
        config.set_view_mapper('pyramid.tests.test_config')
        result = config.registry.getUtility(IViewMapperFactory)
        from pyramid.tests import test_config
        self.assertEqual(result, test_config)


class Test_requestonly(unittest.TestCase):
    def _callFUT(self, view, attr=None):
        from pyramid.config.views import requestonly
        return requestonly(view, attr)

    def test_requestonly_newstyle_class_no_init(self):
        class foo(object):
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_requestonly_newstyle_class_init_toomanyargs(self):
        class foo(object):
            def __init__(self, context, request):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_requestonly_newstyle_class_init_onearg_named_request(self):
        class foo(object):
            def __init__(self, request):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_newstyle_class_init_onearg_named_somethingelse(self):
        class foo(object):
            def __init__(self, req):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_newstyle_class_init_defaultargs_firstname_not_request(self):
        class foo(object):
            def __init__(self, context, request=None):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_newstyle_class_init_defaultargs_firstname_request(self):
        class foo(object):
            def __init__(self, request, foo=1, bar=2):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_newstyle_class_init_firstname_request_with_secondname(self):
        class foo(object):
            def __init__(self, request, two):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_newstyle_class_init_noargs(self):
        class foo(object):
            def __init__():
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_no_init(self):
        class foo:
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_init_toomanyargs(self):
        class foo:
            def __init__(self, context, request):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_init_onearg_named_request(self):
        class foo:
            def __init__(self, request):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_oldstyle_class_init_onearg_named_somethingelse(self):
        class foo:
            def __init__(self, req):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_oldstyle_class_init_defaultargs_firstname_not_request(self):
        class foo:
            def __init__(self, context, request=None):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_init_defaultargs_firstname_request(self):
        class foo:
            def __init__(self, request, foo=1, bar=2):
                """ """
        self.assertTrue(self._callFUT(foo), True)

    def test_oldstyle_class_init_noargs(self):
        class foo:
            def __init__():
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_function_toomanyargs(self):
        def foo(context, request):
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_function_with_attr_false(self):
        def bar(context, request):
            """ """
        def foo(context, request):
            """ """
        foo.bar = bar
        self.assertFalse(self._callFUT(foo, 'bar'))

    def test_function_with_attr_true(self):
        def bar(context, request):
            """ """
        def foo(request):
            """ """
        foo.bar = bar
        self.assertTrue(self._callFUT(foo, 'bar'))

    def test_function_onearg_named_request(self):
        def foo(request):
            """ """
        self.assertTrue(self._callFUT(foo))

    def test_function_onearg_named_somethingelse(self):
        def foo(req):
            """ """
        self.assertTrue(self._callFUT(foo))

    def test_function_defaultargs_firstname_not_request(self):
        def foo(context, request=None):
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_function_defaultargs_firstname_request(self):
        def foo(request, foo=1, bar=2):
            """ """
        self.assertTrue(self._callFUT(foo))

    def test_function_noargs(self):
        def foo():
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_instance_toomanyargs(self):
        class Foo:
            def __call__(self, context, request):
                """ """
        foo = Foo()
        self.assertFalse(self._callFUT(foo))

    def test_instance_defaultargs_onearg_named_request(self):
        class Foo:
            def __call__(self, request):
                """ """
        foo = Foo()
        self.assertTrue(self._callFUT(foo))

    def test_instance_defaultargs_onearg_named_somethingelse(self):
        class Foo:
            def __call__(self, req):
                """ """
        foo = Foo()
        self.assertTrue(self._callFUT(foo))

    def test_instance_defaultargs_firstname_not_request(self):
        class Foo:
            def __call__(self, context, request=None):
                """ """
        foo = Foo()
        self.assertFalse(self._callFUT(foo))

    def test_instance_defaultargs_firstname_request(self):
        class Foo:
            def __call__(self, request, foo=1, bar=2):
                """ """
        foo = Foo()
        self.assertTrue(self._callFUT(foo), True)

    def test_instance_nocall(self):
        class Foo: pass
        foo = Foo()
        self.assertFalse(self._callFUT(foo))

class Test_isexception(unittest.TestCase):
    def _callFUT(self, ob):
        from pyramid.config.views import isexception
        return isexception(ob)

    def test_is_exception_instance(self):
        class E(Exception):
            pass
        e = E()
        self.assertEqual(self._callFUT(e), True)

    def test_is_exception_class(self):
        class E(Exception):
            pass
        self.assertEqual(self._callFUT(E), True)

    def test_is_IException(self):
        from pyramid.interfaces import IException
        self.assertEqual(self._callFUT(IException), True)

    def test_is_IException_subinterface(self):
        from pyramid.interfaces import IException
        class ISubException(IException):
            pass
        self.assertEqual(self._callFUT(ISubException), True)

class TestMultiView(unittest.TestCase):
    def _getTargetClass(self):
        from pyramid.config.views import MultiView
        return MultiView

    def _makeOne(self, name='name'):
        return self._getTargetClass()(name)

    def test_class_implements_ISecuredView(self):
        from zope.interface.verify import verifyClass
        from pyramid.interfaces import ISecuredView
        verifyClass(ISecuredView, self._getTargetClass())

    def test_instance_implements_ISecuredView(self):
        from zope.interface.verify import verifyObject
        from pyramid.interfaces import ISecuredView
        verifyObject(ISecuredView, self._makeOne())

    def test_add(self):
        mv = self._makeOne()
        mv.add('view', 100)
        self.assertEqual(mv.views, [(100, 'view', None)])
        mv.add('view2', 99)
        self.assertEqual(mv.views, [(99, 'view2', None), (100, 'view', None)])
        mv.add('view3', 100, 'text/html')
        self.assertEqual(mv.media_views['text/html'], [(100, 'view3', None)])
        mv.add('view4', 99, 'text/html')
        self.assertEqual(mv.media_views['text/html'],
                         [(99, 'view4', None), (100, 'view3', None)])
        mv.add('view5', 100, 'text/xml')
        self.assertEqual(mv.media_views['text/xml'], [(100, 'view5', None)])
        self.assertEqual(set(mv.accepts), set(['text/xml', 'text/html']))
        self.assertEqual(mv.views, [(99, 'view2', None), (100, 'view', None)])
        mv.add('view6', 98, 'text/*')
        self.assertEqual(mv.views, [(98, 'view6', None),
                                    (99, 'view2', None),
                                    (100, 'view', None)])

    def test_add_with_phash(self):
        mv = self._makeOne()
        mv.add('view', 100, phash='abc')
        self.assertEqual(mv.views, [(100, 'view', 'abc')])
        mv.add('view', 100, phash='abc')
        self.assertEqual(mv.views, [(100, 'view', 'abc')])
        mv.add('view', 100, phash='def')
        self.assertEqual(mv.views, [(100, 'view', 'abc'), (100, 'view', 'def')])
        mv.add('view', 100, phash='abc')
        self.assertEqual(mv.views, [(100, 'view', 'abc'), (100, 'view', 'def')])

    def test_get_views_request_has_no_accept(self):
        request = DummyRequest()
        mv = self._makeOne()
        mv.views = [(99, lambda *arg: None)]
        self.assertEqual(mv.get_views(request), mv.views)

    def test_get_views_no_self_accepts(self):
        request = DummyRequest()
        request.accept = True
        mv = self._makeOne()
        mv.accepts = []
        mv.views = [(99, lambda *arg: None)]
        self.assertEqual(mv.get_views(request), mv.views)

    def test_get_views(self):
        request = DummyRequest()
        request.accept = DummyAccept('text/html')
        mv = self._makeOne()
        mv.accepts = ['text/html']
        mv.views = [(99, lambda *arg: None)]
        html_views = [(98, lambda *arg: None)]
        mv.media_views['text/html'] = html_views
        self.assertEqual(mv.get_views(request), html_views + mv.views)

    def test_get_views_best_match_returns_None(self):
        request = DummyRequest()
        request.accept = DummyAccept(None)
        mv = self._makeOne()
        mv.accepts = ['text/html']
        mv.views = [(99, lambda *arg: None)]
        self.assertEqual(mv.get_views(request), mv.views)

    def test_match_not_found(self):
        from pyramid.httpexceptions import HTTPNotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(HTTPNotFound, mv.match, context, request)

    def test_match_predicate_fails(self):
        from pyramid.httpexceptions import HTTPNotFound
        mv = self._makeOne()
        def view(context, request):
            """ """
        view.__predicated__ = lambda *arg: False
        mv.views = [(100, view, None)]
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(HTTPNotFound, mv.match, context, request)

    def test_match_predicate_succeeds(self):
        mv = self._makeOne()
        def view(context, request):
            """ """
        view.__predicated__ = lambda *arg: True
        mv.views = [(100, view, None)]
        context = DummyContext()
        request = DummyRequest()
        result = mv.match(context, request)
        self.assertEqual(result, view)

    def test_permitted_no_views(self):
        from pyramid.httpexceptions import HTTPNotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(HTTPNotFound, mv.__permitted__, context, request)

    def test_permitted_no_match_with__permitted__(self):
        mv = self._makeOne()
        def view(context, request):
            """ """
        mv.views = [(100, view, None)]
        self.assertEqual(mv.__permitted__(None, None), True)

    def test_permitted(self):
        mv = self._makeOne()
        def view(context, request):
            """ """
        def permitted(context, request):
            return False
        view.__permitted__ = permitted
        mv.views = [(100, view, None)]
        context = DummyContext()
        request = DummyRequest()
        result = mv.__permitted__(context, request)
        self.assertEqual(result, False)

    def test__call__not_found(self):
        from pyramid.httpexceptions import HTTPNotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(HTTPNotFound, mv, context, request)

    def test___call__intermediate_not_found(self):
        from pyramid.exceptions import PredicateMismatch
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view1(context, request):
            raise PredicateMismatch
        def view2(context, request):
            return expected_response
        mv.views = [(100, view1, None), (99, view2, None)]
        response = mv(context, request)
        self.assertEqual(response, expected_response)

    def test___call__raise_not_found_isnt_interpreted_as_pred_mismatch(self):
        from pyramid.httpexceptions import HTTPNotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        def view1(context, request):
            raise  HTTPNotFound
        def view2(context, request):
            """ """
        mv.views = [(100, view1, None), (99, view2, None)]
        self.assertRaises(HTTPNotFound, mv, context, request)

    def test___call__(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view(context, request):
            return expected_response
        mv.views = [(100, view, None)]
        response = mv(context, request)
        self.assertEqual(response, expected_response)

    def test__call_permissive__not_found(self):
        from pyramid.httpexceptions import HTTPNotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(HTTPNotFound, mv, context, request)

    def test___call_permissive_has_call_permissive(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view(context, request):
            """ """
        def permissive(context, request):
            return expected_response
        view.__call_permissive__ = permissive
        mv.views = [(100, view, None)]
        response = mv.__call_permissive__(context, request)
        self.assertEqual(response, expected_response)

    def test___call_permissive_has_no_call_permissive(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view(context, request):
            return expected_response
        mv.views = [(100, view, None)]
        response = mv.__call_permissive__(context, request)
        self.assertEqual(response, expected_response)

    def test__call__with_accept_match(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.accept = DummyAccept('text/html', 'text/xml')
        expected_response = DummyResponse()
        def view(context, request):
            return expected_response
        mv.views = [(100, None)]
        mv.media_views['text/xml'] = [(100, view, None)]
        mv.accepts = ['text/xml']
        response = mv(context, request)
        self.assertEqual(response, expected_response)

    def test__call__with_accept_miss(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.accept = DummyAccept('text/plain', 'text/html')
        expected_response = DummyResponse()
        def view(context, request):
            return expected_response
        mv.views = [(100, view, None)]
        mv.media_views['text/xml'] = [(100, None, None)]
        mv.accepts = ['text/xml']
        response = mv(context, request)
        self.assertEqual(response, expected_response)

class TestViewDeriver(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        self.config = None
        
    def _makeOne(self, **kw):
        kw['registry'] = self.config.registry
        from pyramid.config.views import ViewDeriver
        return ViewDeriver(**kw)
    
    def _makeRequest(self):
        request = DummyRequest()
        request.registry = self.config.registry
        return request

    def _registerLogger(self):
        from pyramid.interfaces import IDebugLogger
        logger = DummyLogger()
        self.config.registry.registerUtility(logger, IDebugLogger)
        return logger

    def _registerSecurityPolicy(self, permissive):
        from pyramid.interfaces import IAuthenticationPolicy
        from pyramid.interfaces import IAuthorizationPolicy
        policy = DummySecurityPolicy(permissive)
        self.config.registry.registerUtility(policy, IAuthenticationPolicy)
        self.config.registry.registerUtility(policy, IAuthorizationPolicy)

    def test_requestonly_function(self):
        response = DummyResponse()
        def view(request):
            return response
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(result(None, None), response)

    def test_requestonly_function_with_renderer(self):
        response = DummyResponse()
        class moo(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, 'OK')
                self.assertEqual(view_inst, view)
                self.assertEqual(ctx, context)
                return response
        def view(request):
            return 'OK'
        deriver = self._makeOne(renderer=moo())
        result = deriver(view)
        self.assertFalse(result.__wraps__ is view)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_requestonly_function_with_renderer_request_override(self):
        def moo(info):
            def inner(value, system):
                self.assertEqual(value, 'OK')
                self.assertEqual(system['request'], request)
                self.assertEqual(system['context'], context)
                return 'moo'
            return inner
        def view(request):
            return 'OK'
        self.config.add_renderer('moo', moo)
        deriver = self._makeOne(renderer='string')
        result = deriver(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        request.override_renderer = 'moo'
        context = testing.DummyResource()
        self.assertEqual(result(context, request).body, b'moo')

    def test_requestonly_function_with_renderer_request_has_view(self):
        response = DummyResponse()
        class moo(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, 'OK')
                self.assertEqual(view_inst, 'view')
                self.assertEqual(ctx, context)
                return response
        def view(request):
            return 'OK'
        deriver = self._makeOne(renderer=moo())
        result = deriver(view)
        self.assertFalse(result.__wraps__ is view)
        request = self._makeRequest()
        request.__view__ = 'view'
        context = testing.DummyResource()
        r = result(context, request)
        self.assertEqual(r, response)
        self.assertFalse(hasattr(request, '__view__'))

    def test_class_without_attr(self):
        response = DummyResponse()
        class View(object):
            def __init__(self, request):
                pass
            def __call__(self):
                return response
        deriver = self._makeOne()
        result = deriver(View)
        request = self._makeRequest()
        self.assertEqual(result(None, request), response)
        self.assertEqual(request.__view__.__class__, View)

    def test_class_with_attr(self):
        response = DummyResponse()
        class View(object):
            def __init__(self, request):
                pass
            def another(self):
                return response
        deriver = self._makeOne(attr='another')
        result = deriver(View)
        request = self._makeRequest()
        self.assertEqual(result(None, request), response)
        self.assertEqual(request.__view__.__class__, View)

    def test_as_function_context_and_request(self):
        def view(context, request):
            return 'OK'
        deriver = self._makeOne()
        result = deriver(view)
        self.assertTrue(result.__wraps__ is view)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        self.assertEqual(view(None, None), 'OK')

    def test_as_function_requestonly(self):
        response = DummyResponse()
        def view(request):
            return response
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), response)

    def test_as_newstyle_class_context_and_request(self):
        response = DummyResponse()
        class view(object):
            def __init__(self, context, request):
                pass
            def __call__(self):
                return response
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        self.assertEqual(result(None, request), response)
        self.assertEqual(request.__view__.__class__, view)

    def test_as_newstyle_class_requestonly(self):
        response = DummyResponse()
        class view(object):
            def __init__(self, context, request):
                pass
            def __call__(self):
                return response
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        self.assertEqual(result(None, request), response)
        self.assertEqual(request.__view__.__class__, view)

    def test_as_oldstyle_class_context_and_request(self):
        response = DummyResponse()
        class view:
            def __init__(self, context, request):
                pass
            def __call__(self):
                return response
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        self.assertEqual(result(None, request), response)
        self.assertEqual(request.__view__.__class__, view)

    def test_as_oldstyle_class_requestonly(self):
        response = DummyResponse()
        class view:
            def __init__(self, context, request):
                pass
            def __call__(self):
                return response
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        self.assertEqual(result(None, request), response)
        self.assertEqual(request.__view__.__class__, view)

    def test_as_instance_context_and_request(self):
        response = DummyResponse()
        class View:
            def __call__(self, context, request):
                return response
        view = View()
        deriver = self._makeOne()
        result = deriver(view)
        self.assertTrue(result.__wraps__ is view)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), response)

    def test_as_instance_requestonly(self):
        response = DummyResponse()
        class View:
            def __call__(self, request):
                return response
        view = View()
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertTrue('test_views' in result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), response)

    def test_with_debug_authorization_no_authpol(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        logger = self._registerLogger()
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): Allowed "
                         "(no authorization policy in use)")

    def test_with_debug_authorization_authn_policy_no_authz_policy(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(debug_authorization=True)
        from pyramid.interfaces import IAuthenticationPolicy
        policy = DummySecurityPolicy(False)
        self.config.registry.registerUtility(policy, IAuthenticationPolicy)
        logger = self._registerLogger()
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): Allowed "
                         "(no authorization policy in use)")

    def test_with_debug_authorization_authz_policy_no_authn_policy(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(debug_authorization=True)
        from pyramid.interfaces import IAuthorizationPolicy
        policy = DummySecurityPolicy(False)
        self.config.registry.registerUtility(policy, IAuthorizationPolicy)
        logger = self._registerLogger()
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): Allowed "
                         "(no authorization policy in use)")

    def test_with_debug_authorization_no_permission(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        self._registerSecurityPolicy(True)
        logger = self._registerLogger()
        deriver = self._makeOne()
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): Allowed ("
                         "no permission registered)")

    def test_debug_auth_permission_authpol_permitted(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        logger = self._registerLogger()
        self._registerSecurityPolicy(True)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result.__call_permissive__.__wraps__, view)
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): True")

    def test_debug_auth_permission_authpol_permitted_no_request(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        logger = self._registerLogger()
        self._registerSecurityPolicy(True)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result.__call_permissive__.__wraps__, view)
        self.assertEqual(result(None, None), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url None (view name "
                         "None against context None): True")

    def test_debug_auth_permission_authpol_denied(self):
        from pyramid.httpexceptions import HTTPForbidden
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        logger = self._registerLogger()
        self._registerSecurityPolicy(False)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result.__call_permissive__.__wraps__, view)
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertRaises(HTTPForbidden, result, None, request)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): False")

    def test_debug_auth_permission_authpol_denied2(self):
        view = lambda *arg: 'OK'
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        self._registerLogger()
        self._registerSecurityPolicy(False)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        permitted = result.__permitted__(None, None)
        self.assertEqual(permitted, False)

    def test_debug_auth_permission_authpol_overridden(self):
        from pyramid.security import NO_PERMISSION_REQUIRED
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = dict(
            debug_authorization=True, reload_templates=True)
        logger = self._registerLogger()
        self._registerSecurityPolicy(False)
        deriver = self._makeOne(permission=NO_PERMISSION_REQUIRED)
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): False")

    def test_secured_view_authn_policy_no_authz_policy(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = {}
        from pyramid.interfaces import IAuthenticationPolicy
        policy = DummySecurityPolicy(False)
        self.config.registry.registerUtility(policy, IAuthenticationPolicy)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)

    def test_secured_view_authz_policy_no_authn_policy(self):
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = {}
        from pyramid.interfaces import IAuthorizationPolicy
        policy = DummySecurityPolicy(False)
        self.config.registry.registerUtility(policy, IAuthorizationPolicy)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertFalse(hasattr(result, '__call_permissive__'))
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), response)

    def test_secured_view_raises_forbidden_no_name(self):
        from pyramid.interfaces import IAuthenticationPolicy
        from pyramid.interfaces import IAuthorizationPolicy
        from pyramid.httpexceptions import HTTPForbidden
        response = DummyResponse()
        view = lambda *arg: response
        self.config.registry.settings = {}
        policy = DummySecurityPolicy(False)
        self.config.registry.registerUtility(policy, IAuthenticationPolicy)
        self.config.registry.registerUtility(policy, IAuthorizationPolicy)
        deriver = self._makeOne(permission='view')
        result = deriver(view)
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        try:
            result(None, request)
        except HTTPForbidden as e:
            self.assertEqual(e.message,
                             'Unauthorized: <lambda> failed permission check')
        else: # pragma: no cover
            raise AssertionError

    def test_secured_view_raises_forbidden_with_name(self):
        from pyramid.interfaces import IAuthenticationPolicy
        from pyramid.interfaces import IAuthorizationPolicy
        from pyramid.httpexceptions import HTTPForbidden
        def myview(request): pass
        self.config.registry.settings = {}
        policy = DummySecurityPolicy(False)
        self.config.registry.registerUtility(policy, IAuthenticationPolicy)
        self.config.registry.registerUtility(policy, IAuthorizationPolicy)
        deriver = self._makeOne(permission='view')
        result = deriver(myview)
        request = self._makeRequest()
        request.view_name = 'view_name'
        request.url = 'url'
        try:
            result(None, request)
        except HTTPForbidden as e:
            self.assertEqual(e.message,
                             'Unauthorized: myview failed permission check')
        else: # pragma: no cover
            raise AssertionError

    def test_predicate_mismatch_view_has_no_name(self):
        from pyramid.exceptions import PredicateMismatch
        response = DummyResponse()
        view = lambda *arg: response
        def predicate1(context, request):
            return False
        deriver = self._makeOne(predicates=[predicate1])
        result = deriver(view)
        request = self._makeRequest()
        request.method = 'POST'
        try:
            result(None, None)
        except PredicateMismatch as e:
            self.assertEqual(e.detail, 'predicate mismatch for view <lambda>')
        else: # pragma: no cover
            raise AssertionError

    def test_predicate_mismatch_view_has_name(self):
        from pyramid.exceptions import PredicateMismatch
        def myview(request): pass
        def predicate1(context, request):
            return False
        deriver = self._makeOne(predicates=[predicate1])
        result = deriver(myview)
        request = self._makeRequest()
        request.method = 'POST'
        try:
            result(None, None)
        except PredicateMismatch as e:
            self.assertEqual(e.detail, 'predicate mismatch for view myview')
        else: # pragma: no cover
            raise AssertionError
            
    def test_with_predicates_all(self):
        response = DummyResponse()
        view = lambda *arg: response
        predicates = []
        def predicate1(context, request):
            predicates.append(True)
            return True
        def predicate2(context, request):
            predicates.append(True)
            return True
        deriver = self._makeOne(predicates=[predicate1, predicate2])
        result = deriver(view)
        request = self._makeRequest()
        request.method = 'POST'
        next = result(None, None)
        self.assertEqual(next, response)
        self.assertEqual(predicates, [True, True])

    def test_with_predicates_checker(self):
        view = lambda *arg: 'OK'
        predicates = []
        def predicate1(context, request):
            predicates.append(True)
            return True
        def predicate2(context, request):
            predicates.append(True)
            return True
        deriver = self._makeOne(predicates=[predicate1, predicate2])
        result = deriver(view)
        request = self._makeRequest()
        request.method = 'POST'
        next = result.__predicated__(None, None)
        self.assertEqual(next, True)
        self.assertEqual(predicates, [True, True])

    def test_with_predicates_notall(self):
        from pyramid.httpexceptions import HTTPNotFound
        view = lambda *arg: 'OK'
        predicates = []
        def predicate1(context, request):
            predicates.append(True)
            return True
        def predicate2(context, request):
            predicates.append(True)
            return False
        deriver = self._makeOne(predicates=[predicate1, predicate2])
        result = deriver(view)
        request = self._makeRequest()
        request.method = 'POST'
        self.assertRaises(HTTPNotFound, result, None, None)
        self.assertEqual(predicates, [True, True])

    def test_with_wrapper_viewname(self):
        from pyramid.response import Response
        from pyramid.interfaces import IView
        from pyramid.interfaces import IViewClassifier
        inner_response = Response('OK')
        def inner_view(context, request):
            return inner_response
        def outer_view(context, request):
            self.assertEqual(request.wrapped_response, inner_response)
            self.assertEqual(request.wrapped_body, inner_response.body)
            self.assertEqual(request.wrapped_view.__original_view__,
                             inner_view)
            return Response('outer ' + request.wrapped_body)
        self.config.registry.registerAdapter(
            outer_view, (IViewClassifier, None, None), IView, 'owrap')
        deriver = self._makeOne(viewname='inner',
                                wrapper_viewname='owrap')
        result = deriver(inner_view)
        self.assertFalse(result is inner_view)
        self.assertEqual(inner_view.__module__, result.__module__)
        self.assertEqual(inner_view.__doc__, result.__doc__)
        request = self._makeRequest()
        response = result(None, request)
        self.assertEqual(response.body, b'outer OK')

    def test_with_wrapper_viewname_notfound(self):
        from pyramid.response import Response
        inner_response = Response('OK')
        def inner_view(context, request):
            return inner_response
        deriver = self._makeOne(viewname='inner', wrapper_viewname='owrap')
        wrapped = deriver(inner_view)
        request = self._makeRequest()
        self.assertRaises(ValueError, wrapped, None, request)

    def test_as_newstyle_class_context_and_request_attr_and_renderer(self):
        response = DummyResponse()
        class renderer(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, {'a':'1'})
                self.assertEqual(view_inst.__class__, View)
                self.assertEqual(ctx, context)
                return response
        class View(object):
            def __init__(self, context, request):
                pass
            def index(self):
                return {'a':'1'}
        deriver = self._makeOne(renderer=renderer(), attr='index')
        result = deriver(View)
        self.assertFalse(result is View)
        self.assertEqual(result.__module__, View.__module__)
        self.assertEqual(result.__doc__, View.__doc__)
        self.assertEqual(result.__name__, View.__name__)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_as_newstyle_class_requestonly_attr_and_renderer(self):
        response = DummyResponse()
        class renderer(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, {'a':'1'})
                self.assertEqual(view_inst.__class__, View)
                self.assertEqual(ctx, context)
                return response
        class View(object):
            def __init__(self, request):
                pass
            def index(self):
                return {'a':'1'}
        deriver = self._makeOne(renderer=renderer(), attr='index')
        result = deriver(View)
        self.assertFalse(result is View)
        self.assertEqual(result.__module__, View.__module__)
        self.assertEqual(result.__doc__, View.__doc__)
        self.assertEqual(result.__name__, View.__name__)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_as_oldstyle_cls_context_request_attr_and_renderer(self):
        response = DummyResponse()
        class renderer(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, {'a':'1'})
                self.assertEqual(view_inst.__class__, View)
                self.assertEqual(ctx, context)
                return response
        class View:
            def __init__(self, context, request):
                pass
            def index(self):
                return {'a':'1'}
        deriver = self._makeOne(renderer=renderer(), attr='index')
        result = deriver(View)
        self.assertFalse(result is View)
        self.assertEqual(result.__module__, View.__module__)
        self.assertEqual(result.__doc__, View.__doc__)
        self.assertEqual(result.__name__, View.__name__)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_as_oldstyle_cls_requestonly_attr_and_renderer(self):
        response = DummyResponse()
        class renderer(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, {'a':'1'})
                self.assertEqual(view_inst.__class__, View)
                self.assertEqual(ctx, context)
                return response
        class View:
            def __init__(self, request):
                pass
            def index(self):
                return {'a':'1'}
        deriver = self._makeOne(renderer=renderer(), attr='index')
        result = deriver(View)
        self.assertFalse(result is View)
        self.assertEqual(result.__module__, View.__module__)
        self.assertEqual(result.__doc__, View.__doc__)
        self.assertEqual(result.__name__, View.__name__)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_as_instance_context_and_request_attr_and_renderer(self):
        response = DummyResponse()
        class renderer(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, {'a':'1'})
                self.assertEqual(view_inst, view)
                self.assertEqual(ctx, context)
                return response
        class View:
            def index(self, context, request):
                return {'a':'1'}
        deriver = self._makeOne(renderer=renderer(), attr='index')
        view = View()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(result.__module__, view.__module__)
        self.assertEqual(result.__doc__, view.__doc__)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_as_instance_requestonly_attr_and_renderer(self):
        response = DummyResponse()
        class renderer(object):
            def render_view(inself, req, resp, view_inst, ctx):
                self.assertEqual(req, request)
                self.assertEqual(resp, {'a':'1'})
                self.assertEqual(view_inst, view)
                self.assertEqual(ctx, context)
                return response
        class View:
            def index(self, request):
                return {'a':'1'}
        deriver = self._makeOne(renderer=renderer(), attr='index')
        view = View()
        result = deriver(view)
        self.assertFalse(result is view)
        self.assertEqual(result.__module__, view.__module__)
        self.assertEqual(result.__doc__, view.__doc__)
        request = self._makeRequest()
        context = testing.DummyResource()
        self.assertEqual(result(context, request), response)

    def test_with_view_mapper_config_specified(self):
        response = DummyResponse()
        class mapper(object):
            def __init__(self, **kw):
                self.kw = kw
            def __call__(self, view):
                def wrapped(context, request):
                    return response
                return wrapped
        def view(context, request): return 'NOTOK'
        deriver = self._makeOne(mapper=mapper)
        result = deriver(view)
        self.assertFalse(result.__wraps__ is view)
        self.assertEqual(result(None, None), response)

    def test_with_view_mapper_view_specified(self):
        from pyramid.response import Response
        response = Response()
        def mapper(**kw):
            def inner(view):
                def superinner(context, request):
                    self.assertEqual(request, None)
                    return response
                return superinner
            return inner
        def view(context, request): return 'NOTOK'
        view.__view_mapper__ = mapper
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result.__wraps__ is view)
        self.assertEqual(result(None, None), response)

    def test_with_view_mapper_default_mapper_specified(self):
        from pyramid.response import Response
        response = Response()
        def mapper(**kw):
            def inner(view):
                def superinner(context, request):
                    self.assertEqual(request, None)
                    return  response
                return superinner
            return inner
        self.config.set_view_mapper(mapper)
        def view(context, request): return 'NOTOK'
        deriver = self._makeOne()
        result = deriver(view)
        self.assertFalse(result.__wraps__ is view)
        self.assertEqual(result(None, None), response)

    def test_attr_wrapped_view_branching_default_phash(self):
        from pyramid.config.util import DEFAULT_PHASH
        def view(context, request): pass
        deriver = self._makeOne(phash=DEFAULT_PHASH)
        result = deriver(view)
        self.assertEqual(result.__wraps__, view)

    def test_attr_wrapped_view_branching_nondefault_phash(self):
        def view(context, request): pass
        deriver = self._makeOne(phash='nondefault')
        result = deriver(view)
        self.assertNotEqual(result, view)

    def test_http_cached_view_integer(self):
        import datetime
        from pyramid.response import Response
        response = Response('OK')
        def inner_view(context, request):
            return response
        deriver = self._makeOne(http_cache=3600)
        result = deriver(inner_view)
        self.assertFalse(result is inner_view)
        self.assertEqual(inner_view.__module__, result.__module__)
        self.assertEqual(inner_view.__doc__, result.__doc__)
        request = self._makeRequest()
        when = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        result = result(None, request)
        self.assertEqual(result, response)
        headers = dict(result.headerlist)
        expires = parse_httpdate(headers['Expires'])
        assert_similar_datetime(expires, when)
        self.assertEqual(headers['Cache-Control'], 'max-age=3600')
        
    def test_http_cached_view_timedelta(self):
        import datetime
        from pyramid.response import Response
        response = Response('OK')
        def inner_view(context, request):
            return response
        deriver = self._makeOne(http_cache=datetime.timedelta(hours=1))
        result = deriver(inner_view)
        self.assertFalse(result is inner_view)
        self.assertEqual(inner_view.__module__, result.__module__)
        self.assertEqual(inner_view.__doc__, result.__doc__)
        request = self._makeRequest()
        when = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        result = result(None, request)
        self.assertEqual(result, response)
        headers = dict(result.headerlist)
        expires = parse_httpdate(headers['Expires'])
        assert_similar_datetime(expires, when)
        self.assertEqual(headers['Cache-Control'], 'max-age=3600')

    def test_http_cached_view_tuple(self):
        import datetime
        from pyramid.response import Response
        response = Response('OK')
        def inner_view(context, request):
            return response
        deriver = self._makeOne(http_cache=(3600, {'public':True}))
        result = deriver(inner_view)
        self.assertFalse(result is inner_view)
        self.assertEqual(inner_view.__module__, result.__module__)
        self.assertEqual(inner_view.__doc__, result.__doc__)
        request = self._makeRequest()
        when = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        result = result(None, request)
        self.assertEqual(result, response)
        headers = dict(result.headerlist)
        expires = parse_httpdate(headers['Expires'])
        assert_similar_datetime(expires, when)
        self.assertEqual(headers['Cache-Control'], 'max-age=3600, public')

    def test_http_cached_view_tuple_seconds_None(self):
        from pyramid.response import Response
        response = Response('OK')
        def inner_view(context, request):
            return response
        deriver = self._makeOne(http_cache=(None, {'public':True}))
        result = deriver(inner_view)
        self.assertFalse(result is inner_view)
        self.assertEqual(inner_view.__module__, result.__module__)
        self.assertEqual(inner_view.__doc__, result.__doc__)
        request = self._makeRequest()
        result = result(None, request)
        self.assertEqual(result, response)
        headers = dict(result.headerlist)
        self.assertFalse('Expires' in headers)
        self.assertEqual(headers['Cache-Control'], 'public')

    def test_http_cached_view_prevent_auto_set(self):
        from pyramid.response import Response
        response = Response()
        response.cache_control.prevent_auto = True
        def inner_view(context, request):
            return response
        deriver = self._makeOne(http_cache=3600)
        result = deriver(inner_view)
        request = self._makeRequest()
        result = result(None, request)
        self.assertEqual(result, response) # doesn't blow up
        headers = dict(result.headerlist)
        self.assertFalse('Expires' in headers)
        self.assertFalse('Cache-Control' in headers)

    def test_http_cached_prevent_http_cache_in_settings(self):
        self.config.registry.settings['prevent_http_cache'] = True
        from pyramid.response import Response
        response = Response()
        def inner_view(context, request):
            return response
        deriver = self._makeOne(http_cache=3600)
        result = deriver(inner_view)
        request = self._makeRequest()
        result = result(None, request)
        self.assertEqual(result, response)
        headers = dict(result.headerlist)
        self.assertFalse('Expires' in headers)
        self.assertFalse('Cache-Control' in headers)

    def test_http_cached_view_bad_tuple(self):
        deriver = self._makeOne(http_cache=(None,))
        def view(request): pass
        self.assertRaises(ConfigurationError, deriver, view)

class TestDefaultViewMapper(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.registry = self.config.registry 

    def tearDown(self):
        del self.registry
        testing.tearDown()

    def _makeOne(self, **kw):
        from pyramid.config.views import DefaultViewMapper
        kw['registry'] = self.registry
        return DefaultViewMapper(**kw)

    def _makeRequest(self):
        request = DummyRequest()
        request.registry = self.registry
        return request

    def test_view_as_function_context_and_request(self):
        def view(context, request):
            return 'OK'
        mapper = self._makeOne()
        result = mapper(view)
        self.assertTrue(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test__view_as_function_with_attr(self):
        def view(context, request):
            """ """
        mapper = self._makeOne(attr='__name__')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertRaises(TypeError, result, None, request)

    def test_view_as_function_requestonly(self):
        def view(request):
            return 'OK'
        mapper = self._makeOne()
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_function_requestonly_with_attr(self):
        def view(request):
            """ """
        mapper = self._makeOne(attr='__name__')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertRaises(TypeError, result, None, request)

    def test_view_as_newstyle_class_context_and_request(self):
        class view(object):
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        mapper = self._makeOne()
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_newstyle_class_context_and_request_with_attr(self):
        class view(object):
            def __init__(self, context, request):
                pass
            def index(self):
                return 'OK'
        mapper = self._makeOne(attr='index')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_newstyle_class_requestonly(self):
        class view(object):
            def __init__(self, request):
                pass
            def __call__(self):
                return 'OK'
        mapper = self._makeOne()
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_newstyle_class_requestonly_with_attr(self):
        class view(object):
            def __init__(self, request):
                pass
            def index(self):
                return 'OK'
        mapper = self._makeOne(attr='index')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_oldstyle_class_context_and_request(self):
        class view:
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        mapper = self._makeOne()
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_oldstyle_class_context_and_request_with_attr(self):
        class view:
            def __init__(self, context, request):
                pass
            def index(self):
                return 'OK'
        mapper = self._makeOne(attr='index')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_oldstyle_class_requestonly(self):
        class view:
            def __init__(self, request):
                pass
            def __call__(self):
                return 'OK'
        mapper = self._makeOne()
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_oldstyle_class_requestonly_with_attr(self):
        class view:
            def __init__(self, request):
                pass
            def index(self):
                return 'OK'
        mapper = self._makeOne(attr='index')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_instance_context_and_request(self):
        class View:
            def __call__(self, context, request):
                return 'OK'
        view = View()
        mapper = self._makeOne()
        result = mapper(view)
        self.assertTrue(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_instance_context_and_request_and_attr(self):
        class View:
            def index(self, context, request):
                return 'OK'
        view = View()
        mapper = self._makeOne(attr='index')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_instance_requestonly(self):
        class View:
            def __call__(self, request):
                return 'OK'
        view = View()
        mapper = self._makeOne()
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

    def test_view_as_instance_requestonly_with_attr(self):
        class View:
            def index(self, request):
                return 'OK'
        view = View()
        mapper = self._makeOne(attr='index')
        result = mapper(view)
        self.assertFalse(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request), 'OK')

class Test_preserve_view_attrs(unittest.TestCase):
    def _callFUT(self, view, wrapped_view):
        from pyramid.config.views import preserve_view_attrs
        return preserve_view_attrs(view, wrapped_view)

    def test_it_same(self):
        def view(context, request):
            """ """
        result = self._callFUT(view, view)
        self.assertTrue(result is view)

    def test_it_view_is_None(self):
        def view(context, request):
            """ """
        result = self._callFUT(None, view)
        self.assertTrue(result is view)

    def test_it_different_with_existing_original_view(self):
        def view1(context, request): pass
        view1.__original_view__ = 'abc'
        def view2(context, request): pass
        result = self._callFUT(view1, view2)
        self.assertEqual(result.__original_view__, 'abc')
        self.assertFalse(result is view1)

    def test_it_different(self):
        class DummyView1:
            """ 1 """
            __name__ = '1'
            __module__ = '1'
            def __call__(self, context, request):
                """ """
            def __call_permissive__(self, context, request):
                """ """
            def __predicated__(self, context, request):
                """ """
            def __permitted__(self, context, request):
                """ """
        class DummyView2:
            """ 2 """
            __name__ = '2'
            __module__ = '2'
            def __call__(self, context, request):
                """ """
            def __call_permissive__(self, context, request):
                """ """
            def __predicated__(self, context, request):
                """ """
            def __permitted__(self, context, request):
                """ """
        view1 = DummyView1()
        view2 = DummyView2()
        result = self._callFUT(view2, view1)
        self.assertEqual(result, view1)
        self.assertTrue(view1.__original_view__ is view2)
        self.assertTrue(view1.__doc__ is view2.__doc__)
        self.assertTrue(view1.__module__ is view2.__module__)
        self.assertTrue(view1.__name__ is view2.__name__)
        self.assertTrue(view1.__call_permissive__.im_func is
                        view2.__call_permissive__.im_func)
        self.assertTrue(view1.__permitted__.im_func is
                        view2.__permitted__.im_func)
        self.assertTrue(view1.__predicated__.im_func is
                        view2.__predicated__.im_func)


class TestStaticURLInfo(unittest.TestCase):
    def _getTargetClass(self):
        from pyramid.config.views import StaticURLInfo
        return StaticURLInfo
    
    def _makeOne(self):
        return self._getTargetClass()()

    def _makeConfig(self, registrations=None):
        config = DummyConfig()
        registry = DummyRegistry()
        if registrations is not None:
            registry._static_url_registrations = registrations
        config.registry = registry
        return config

    def _makeRequest(self):
        request = DummyRequest()
        request.registry = DummyRegistry()
        return request

    def _assertRegistrations(self, config, expected):
        self.assertEqual(config.registry._static_url_registrations, expected)

    def test_verifyClass(self):
        from pyramid.interfaces import IStaticURLInfo
        from zope.interface.verify import verifyClass
        verifyClass(IStaticURLInfo, self._getTargetClass())

    def test_verifyObject(self):
        from pyramid.interfaces import IStaticURLInfo
        from zope.interface.verify import verifyObject
        verifyObject(IStaticURLInfo, self._makeOne())

    def test_generate_missing(self):
        inst = self._makeOne()
        request = self._makeRequest()
        self.assertRaises(ValueError, inst.generate, 'path', request)

    def test_generate_registration_miss(self):
        inst = self._makeOne()
        registrations = [(None, 'spec', 'route_name'),
                         ('http://example.com/foo/', 'package:path/', None)]
        inst._get_registrations = lambda *x: registrations
        request = self._makeRequest()
        result = inst.generate('package:path/abc', request)
        self.assertEqual(result, 'http://example.com/foo/abc')

    def test_generate_registration_no_registry_on_request(self):
        inst = self._makeOne()
        registrations = [('http://example.com/foo/', 'package:path/', None)]
        inst._get_registrations = lambda *x: registrations
        request = self._makeRequest()
        del request.registry
        result = inst.generate('package:path/abc', request)
        self.assertEqual(result, 'http://example.com/foo/abc')

    def test_generate_slash_in_name1(self):
        inst = self._makeOne()
        registrations = [('http://example.com/foo/', 'package:path/', None)]
        inst._get_registrations = lambda *x: registrations
        request = self._makeRequest()
        result = inst.generate('package:path/abc', request)
        self.assertEqual(result, 'http://example.com/foo/abc')

    def test_generate_slash_in_name2(self):
        inst = self._makeOne()
        registrations = [('http://example.com/foo/', 'package:path/', None)]
        inst._get_registrations = lambda *x: registrations
        request = self._makeRequest()
        result = inst.generate('package:path/', request)
        self.assertEqual(result, 'http://example.com/foo/')

    def test_generate_route_url(self):
        inst = self._makeOne()
        registrations = [(None, 'package:path/', '__viewname/')]
        inst._get_registrations = lambda *x: registrations
        def route_url(n, **kw):
            self.assertEqual(n, '__viewname/')
            self.assertEqual(kw, {'subpath':'abc', 'a':1})
            return 'url'
        request = self._makeRequest()
        request.route_url = route_url
        result = inst.generate('package:path/abc', request, a=1)
        self.assertEqual(result, 'url')

    def test_add_already_exists(self):
        inst = self._makeOne()
        config = self._makeConfig(
            [('http://example.com/', 'package:path/', None)])
        inst.add(config, 'http://example.com', 'anotherpackage:path')
        expected = [('http://example.com/',  'anotherpackage:path/', None)]
        self._assertRegistrations(config, expected)

    def test_add_url_withendslash(self):
        inst = self._makeOne()
        config = self._makeConfig()
        inst.add(config, 'http://example.com/', 'anotherpackage:path')
        expected = [('http://example.com/', 'anotherpackage:path/', None)]
        self._assertRegistrations(config, expected)

    def test_add_url_noendslash(self):
        inst = self._makeOne()
        config = self._makeConfig()
        inst.add(config, 'http://example.com', 'anotherpackage:path')
        expected = [('http://example.com/', 'anotherpackage:path/', None)]
        self._assertRegistrations(config, expected)

    def test_add_viewname(self):
        from pyramid.security import NO_PERMISSION_REQUIRED
        from pyramid.static import static_view
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1)
        expected = [(None, 'anotherpackage:path/', '__view/')]
        self._assertRegistrations(config, expected)
        self.assertEqual(config.route_args, ('__view/', 'view/*subpath'))
        self.assertEqual(config.view_kw['permission'], NO_PERMISSION_REQUIRED)
        self.assertEqual(config.view_kw['view'].__class__, static_view)

    def test_add_viewname_with_route_prefix(self):
        config = self._makeConfig()
        config.route_prefix = '/abc'
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path',)
        expected = [(None, 'anotherpackage:path/', '__/abc/view/')]
        self._assertRegistrations(config, expected)
        self.assertEqual(config.route_args, ('__/abc/view/', 'view/*subpath'))

    def test_add_viewname_with_permission(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 permission='abc')
        self.assertEqual(config.view_kw['permission'], 'abc')

    def test_add_viewname_with_view_permission(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 view_permission='abc')
        self.assertEqual(config.view_kw['permission'], 'abc')

    def test_add_viewname_with_view_context(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 view_context=DummyContext)
        self.assertEqual(config.view_kw['context'], DummyContext)

    def test_add_viewname_with_view_for(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 view_for=DummyContext)
        self.assertEqual(config.view_kw['context'], DummyContext)

    def test_add_viewname_with_for_(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 for_=DummyContext)
        self.assertEqual(config.view_kw['context'], DummyContext)

    def test_add_viewname_with_view_renderer(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 view_renderer='mypackage:templates/index.pt')
        self.assertEqual(config.view_kw['renderer'],
                         'mypackage:templates/index.pt')

    def test_add_viewname_with_renderer(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 renderer='mypackage:templates/index.pt')
        self.assertEqual(config.view_kw['renderer'],
                         'mypackage:templates/index.pt')

    def test_add_viewname_with_view_attr(self):
        config = self._makeConfig()
        inst = self._makeOne()
        inst.add(config, 'view', 'anotherpackage:path', cache_max_age=1,
                 view_attr='attr')
        self.assertEqual(config.view_kw['attr'], 'attr')

class DummyRegistry:
    pass

class DummyRequest:
    subpath = ()
    matchdict = None
    def __init__(self, environ=None):
        if environ is None:
            environ = {}
        self.environ = environ
        self.params = {}
        self.cookies = {}

class DummyContext:
    pass

from zope.interface import implementer
from pyramid.interfaces import IResponse
@implementer(IResponse)
class DummyResponse(object):
    pass

class DummyAccept(object):
    def __init__(self, *matches):
        self.matches = list(matches)

    def best_match(self, offered):
        if self.matches:
            for match in self.matches:
                if match in offered:
                    self.matches.remove(match)
                    return match
    def __contains__(self, val):
        return val in self.matches

class DummyLogger:
    def __init__(self):
        self.messages = []
    def info(self, msg):
        self.messages.append(msg)
    warn = info
    debug = info

class DummySecurityPolicy:
    def __init__(self, permitted=True):
        self.permitted = permitted

    def effective_principals(self, request):
        return []

    def permits(self, context, principals, permission):
        return self.permitted

class DummyConfig:
    route_prefix = ''
    def add_route(self, *args, **kw):
        self.route_args = args
        self.route_kw = kw

    def add_view(self, *args, **kw):
        self.view_args = args
        self.view_kw = kw

    def action(self, discriminator, callable):
        callable()

from zope.interface import implementer
from pyramid.interfaces import IMultiView
@implementer(IMultiView)
class DummyMultiView:
    def __init__(self):
        self.views = []
        self.name = 'name'
    def add(self, view, order, accept=None, phash=None):
        self.views.append((view, accept, phash))
    def __call__(self, context, request):
        return 'OK1'
    def __permitted__(self, context, request):
        """ """

def parse_httpdate(s):
    import datetime
    # cannot use %Z, must use literal GMT; Jython honors timezone
    # but CPython does not
    return datetime.datetime.strptime(s, "%a, %d %b %Y %H:%M:%S GMT")

def assert_similar_datetime(one, two):
    for attr in ('year', 'month', 'day', 'hour', 'minute'):
        one_attr = getattr(one, attr)
        two_attr = getattr(two, attr)
        if not one_attr == two_attr: # pragma: no cover
            raise AssertionError('%r != %r in %s' % (one_attr, two_attr, attr))

class DummyStaticURLInfo:
    def __init__(self):
        self.added = []

    def add(self, config, name, spec, **kw):
        self.added.append((config, name, spec, kw))
