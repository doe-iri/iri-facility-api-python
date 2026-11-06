#!/usr/bin/env python3
"""Idempotency-Key handling for a deployment with no backing store."""

import unittest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.idempotency import run_with_idempotency
from app.routers.error_handlers import install_error_handlers


class TestNoStoreConfigured(unittest.TestCase):
    """A key sent to a deployment without a store is rejected before the adapter runs."""

    def setUp(self):
        self.adapter_fn = AsyncMock()
        app = FastAPI()
        install_error_handlers(app)

        @app.post("/job")
        async def submit():
            return await run_with_idempotency(None, "cache-key", "body-hash", self.adapter_fn)

        self.response = TestClient(app).post("/job")

    def test_returns_400_problem(self):
        self.assertEqual(self.response.status_code, 400)
        self.assertEqual(self.response.headers["content-type"], "application/problem+json")
        self.assertEqual(self.response.json()["status"], 400)

    def test_detail_names_header_without_server_configuration(self):
        detail = self.response.json()["detail"]
        self.assertIn("Idempotency-Key", detail)
        self.assertIn("not processed", detail)
        self.assertNotIn("IRI_IDEMPOTENCY_STORE", detail)

    def test_adapter_is_not_called(self):
        self.adapter_fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
