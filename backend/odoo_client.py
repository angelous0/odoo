"""
Odoo 10 XML-RPC Client with retry, timeout, and error handling.
"""
import xmlrpc.client
import time
import logging
import ssl

logger = logging.getLogger(__name__)

# Allow unverified SSL for self-signed certs (common in Odoo deployments)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


class OdooClient:
    """XML-RPC client for Odoo 10."""

    def __init__(self, url, timeout=120):
        self.url = url.rstrip('/')
        self.timeout = timeout
        self._common = None
        self._object = None

    @property
    def common(self):
        if self._common is None:
            self._common = xmlrpc.client.ServerProxy(
                f'{self.url}/xmlrpc/2/common',
                context=ssl_context,
            )
        return self._common

    @property
    def object(self):
        if self._object is None:
            self._object = xmlrpc.client.ServerProxy(
                f'{self.url}/xmlrpc/2/object',
                context=ssl_context,
                allow_none=True,
            )
        return self._object

    def authenticate(self, db, login, password):
        """Authenticate and return uid."""
        for attempt in range(3):
            try:
                uid = self.common.authenticate(db, login, password, {})
                if uid:
                    logger.info(f"Authenticated as uid={uid} ({login})")
                    return uid
                raise Exception(f"Authentication failed for {login}")
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"Auth attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def execute_kw(self, db, uid, password, model, method, args=None, kwargs=None):
        """Execute Odoo method with retry and backoff."""
        args = args or []
        kwargs = kwargs or {}
        for attempt in range(3):
            try:
                result = self.object.execute_kw(db, uid, password, model, method, args, kwargs)
                return result
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"execute_kw {model}.{method} attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"execute_kw {model}.{method} failed after 3 attempts: {e}")
                    raise

    def search_read(self, db, uid, password, model, domain, fields, limit=0, offset=0, order=None, context=None):
        """Convenience method for search_read."""
        kw = {'fields': fields, 'limit': limit, 'offset': offset}
        if order:
            kw['order'] = order
        if context:
            kw['context'] = context
        return self.execute_kw(db, uid, password, model, 'search_read', [domain], kw)

    def search_count(self, db, uid, password, model, domain, context=None):
        """Count records matching domain."""
        kw = {}
        if context:
            kw['context'] = context
        return self.execute_kw(db, uid, password, model, 'search_count', [domain], kw)

    def read(self, db, uid, password, model, ids, fields, context=None):
        """Read specific records by ids."""
        kw = {'fields': fields}
        if context:
            kw['context'] = context
        return self.execute_kw(db, uid, password, model, 'read', [ids], kw)
