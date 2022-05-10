import json
from typing import Type

from .clients import HttpClient


class ReversedJSONEncoder(json.JSONEncoder):
    def encode(self, o: object) -> str:
        # Reverse the result.
        return super().encode(o)[::-1]


async def test_uses_encoder(http_client_class: Type[HttpClient]):
    http_client = http_client_class(json_encoder=ReversedJSONEncoder)

    response = await http_client.query(
        query="{ hello }",
    )

    assert response.status_code == 200
    assert response.text[::-1] == '{"data": {"hello": "Hello world"}}'


async def test_can_pass_dumps_params(http_client_class: Type[HttpClient]):
    http_client = http_client_class(json_dumps_params={"separators": (",", "👉 ")})

    response = await http_client.query(
        query="{ hello }",
    )

    assert response.status_code == 200
    assert response.text == '{"data"👉 {"hello"👉 "Hello world"}}'
