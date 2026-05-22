import re
import typing
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse


class RangeRequestMiddleware:
    """Add HTTP range request support to Django's dev file server.

    Django's built-in static/media serving ignores Range headers, which
    means COG files can't be range-fetched by Mapbox/MapLibre in development.
    This middleware intercepts 200 responses that carry a Range request header,
    slices the content, and returns a proper 206 Partial Content response.

    Only intended for development (add inside the DEBUG block in settings).
    In production, Azure Blob Storage handles range requests natively.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        range_header = request.META.get("HTTP_RANGE", "")
        if not range_header or response.status_code != 200:
            response["Accept-Ranges"] = "bytes"
            return response

        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match:
            response["Accept-Ranges"] = "bytes"
            return response

        # StreamingHttpResponse (e.g. FileResponse from static file serving)
        # doesn't have .content — consume the iterator.
        content = (
            b"".join(typing.cast("typing.Iterator[bytes]", response.streaming_content))
            if isinstance(response, StreamingHttpResponse)
            else response.content
        )
        total = len(content)

        start_str, end_str = match.groups()
        if start_str:
            start = int(start_str)
            end = int(end_str) if end_str else total - 1
        else:
            # suffix-length form: bytes=-N  →  last N bytes
            start = total - int(end_str)
            end = total - 1

        end = min(end, total - 1)

        if start > end or start >= total:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{total}"})

        partial = HttpResponse(
            content[start : end + 1],
            status=206,
            content_type=response.get("Content-Type", "application/octet-stream"),
        )
        partial["Content-Range"] = f"bytes {start}-{end}/{total}"
        partial["Content-Length"] = end - start + 1
        partial["Accept-Ranges"] = "bytes"
        return partial
