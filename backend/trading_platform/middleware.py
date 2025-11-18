"""
Custom middleware for cache control
"""

class NoCacheMiddleware:
    """
    Middleware to add aggressive no-cache headers for HTML files
    This ensures browsers ALWAYS revalidate and never serve stale cached content
    
    CRITICAL: This prevents "Internal Server Error" from stale cached HTML
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add AGGRESSIVE no-cache headers for HTML files and root path
        # This forces browsers to ALWAYS check server for latest version
        if (response.get('Content-Type', '').startswith('text/html') or 
            request.path == '/' or 
            request.path.endswith('.html')):
            
            # Triple-layer cache prevention (HTTP/1.1, HTTP/1.0, Proxies)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            # Force revalidation on every request
            response['Last-Modified'] = 'Wed, 01 Jan 2025 00:00:00 GMT'
            response['ETag'] = None  # Disable ETag caching
            
            # Prevent proxy/CDN caching
            response['Surrogate-Control'] = 'no-store'
            
            # Add version header for debugging
            import time
            response['X-App-Version'] = str(int(time.time()))
        
        return response
