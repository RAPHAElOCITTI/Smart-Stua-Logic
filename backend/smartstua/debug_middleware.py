import traceback
import os

class TracebackDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        tb_text = traceback.format_exc()
        try:
            # Save the exception and traceback to a temp file
            log_path = '/tmp/last_error.txt'
            # If on Windows/local, fallback to current directory
            if os.name == 'nt':
                log_path = 'last_error.txt'
            with open(log_path, 'w') as f:
                f.write(f"URL: {request.build_absolute_uri()}\n")
                f.write(f"Method: {request.method}\n")
                f.write(f"Exception: {str(exception)}\n\n")
                f.write(tb_text)
        except Exception:
            pass
        return None
