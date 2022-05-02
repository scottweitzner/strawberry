from __future__ import annotations

from io import BytesIO
from json import dumps
from typing import Dict, Optional, Union

from typing_extensions import Literal

from django.core.exceptions import BadRequest, SuspiciousOperation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404, HttpRequest, HttpResponse
from django.test.client import RequestFactory

from strawberry.django.views import GraphQLView as BaseGraphQLView

from ..context import get_context
from ..schema import Query, schema
from . import JSON, HttpClient, Response


class GraphQLView(BaseGraphQLView):
    def get_root_value(self, request):
        return Query()

    def get_context(self, request: HttpRequest, response: HttpResponse) -> object:
        context = {"request": request, "response": response}

        return get_context(context)


class DjangoHttpClient(HttpClient):
    def __init__(self, graphiql: bool = True, allow_queries_via_get: bool = True):
        self.graphiql = graphiql
        self.allow_queries_via_get = allow_queries_via_get

    def _get_header_name(self, key: str) -> str:
        return f"HTTP_{key.upper().replace('-', '_')}"

    def _get_headers(
        self,
        method: Literal["get", "post"],
        headers: Optional[Dict[str, str]],
        files: Optional[Dict[str, BytesIO]],
    ) -> Dict[str, str]:
        headers = headers or {}
        headers = {self._get_header_name(key): value for key, value in headers.items()}

        return super()._get_headers(method=method, headers=headers, files=files)

    async def _do_request(self, request: RequestFactory) -> Response:
        try:
            response = GraphQLView.as_view(
                schema=schema,
                graphiql=self.graphiql,
                allow_queries_via_get=self.allow_queries_via_get,
            )(request)
        except Http404:
            return Response(status_code=404, data=b"Not found")
        except (BadRequest, SuspiciousOperation) as e:
            return Response(status_code=400, data=e.args[0].encode())
        else:
            return Response(status_code=response.status_code, data=response.content)

    async def _graphql_request(
        self,
        method: Literal["get", "post"],
        query: Optional[str] = None,
        variables: Optional[Dict[str, object]] = None,
        files: Optional[Dict[str, BytesIO]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Response:
        headers = self._get_headers(method=method, headers=headers, files=files)
        additional_arguments = {**kwargs, **headers}

        body = self._build_body(
            query=query, variables=variables, files=files, method=method
        )

        data: Union[Dict[str, object], str, None] = None

        if body and files:
            files = {
                name: SimpleUploadedFile(name, file.read())
                for name, file in files.items()
            }
            body.update(files)
        else:
            additional_arguments["content_type"] = "application/json"

        if body:
            data = body if files or method == "get" else dumps(body)

        factory = RequestFactory()
        request = getattr(factory, method)(
            "/graphql",
            data=data,
            **additional_arguments,
        )

        return await self._do_request(request)

    async def request(
        self,
        url: str,
        method: Literal["get", "post", "patch", "put", "delete"],
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        headers = self._get_headers(
            method=method,  # type: ignore
            headers=headers,
            files=None,
        )

        factory = RequestFactory()
        request = getattr(factory, method)(url, **headers)

        return await self._do_request(request)

    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        return await self.request(url, "get", headers=headers)

    async def post(
        self,
        url: str,
        data: Optional[bytes] = None,
        json: Optional[JSON] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        headers = self._get_headers(method="post", headers=headers, files=None)

        additional_arguments = {**headers}

        body = data or dumps(json)

        if headers.get("HTTP_CONTENT_TYPE"):
            additional_arguments["content_type"] = headers["HTTP_CONTENT_TYPE"]

        factory = RequestFactory()
        request = factory.post(
            url,
            data=body,
            **additional_arguments,
        )

        return await self._do_request(request)
