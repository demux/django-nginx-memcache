import logging

from django.conf import settings

from .cache import cache_response

is_enabled = getattr(settings, 'CACHE_NGINX', True)

do_cache_https = getattr(settings, 'CACHE_NGINX_INCLUDE_HTTPS', True)

https_headers_to_check = getattr(
    settings,
    'CACHE_NGINX_ALTERNATIVE_SSL_HEADERS',
    (
        ('X-Forwarded-Proto', 'HTTPS'),
        ('X-Forwarded-SSL', 'on')
    )
)


class UpdateCacheMiddleware(object):
    """Updates the cache cache with the response of the request.

    It is of _paramount_ importance that the generated cache_key matches
    exactly the key generated by your web server (nginx) to lookup the page
    from the cache.

    Remember to set CACHE_NGINX_ALIAS to a cache backend that uses memcache.

    The middleware must be at the top of settings.MIDDLEWARE_CLASSES
    to be called last during the response phase.

    """

    def __init__(
            self,
            cache_timeout,
            page_version_fn,
            anonymous_only,
            lookup_identifier=None,
            supplementary_identifier=None
        ):
        """Initialize middleware. Args:
            * cache_timeout - seconds after which the cached response expires
            * page_version_fn - return a value to version the view based on
                    the request.
            * anonymous_only - only cache if the user is anonymous
            * lookup_identifer - for populating the lookup table;
                see models.CachedPageRecord. If not specified in the decorator,
                the value of request.get_host() will be used, which is a good
                thing to use anyway.
            * supplementary_identifier - entirely optional scoping variable.
                For populating the lookup table; see models.CachedPageRecord

        """

        self.cache_timeout = cache_timeout
        self.page_version_fn = page_version_fn
        self.anonymous_only = anonymous_only
        self.lookup_identifier = lookup_identifier
        self.supplementary_identifier = supplementary_identifier

    def process_response(self, request, response):
        """Sets the cache, if needed."""
        if not is_enabled or request.method != 'GET' or (
            response.status_code != 200):
            # HTTPMiddleware, throws the body of a HEAD-request away before
            # this middleware gets a chance to cache it.
            return response

        # Logged in users don't cause caching if anonymous_only is set.
        if self.anonymous_only and request.user.is_authenticated():
            return response

        logging.info("do_cache_https: %s" % do_cache_https)
        if not do_cache_https:
            # If cacheing of pages accessed over https, skip cacheing
            if request.is_secure():
                logging.info("request.is_secure() == True")
                return response
            # As of Django 1.4, request.is_secure() checks for things like
            # X-Forwarded-Proto and X-Forwarded-SSL, but this caters for
            # pre-1.4 projects:
            logging.info("https_headers_to_check: %s" % https_headers_to_check)
            for header, significant_value in https_headers_to_check:
                # convert header to Django's request.META format
                _header = 'HTTP_' + header.upper().replace('-', '_')
                logging.info('_header: %s' % _header)
                if request.META.get(_header, None).lower() == significant_value.lower():
                    logging.info("%s %s %s " % (
                        _header,
                        request.META.get(_header, None).lower(),
                        significant_value.lower())
                    )
                    return response

        # Otherwise, we do want to cache the response.
        cache_response(
            request,
            response,
            cache_timeout=self.cache_timeout,
            page_version_fn=self.page_version_fn,
            lookup_identifier=self.lookup_identifier,
            supplementary_identifier=self.supplementary_identifier
        )
        return response
