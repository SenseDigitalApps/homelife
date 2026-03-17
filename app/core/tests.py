from __future__ import annotations

import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from devices.models import Device
from recommendations.models import Recommendation


class SmokeApiTests(APITestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["service"], "medsync-api")

    def test_schema_endpoint_is_available(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuthFlowTests(APITestCase):
    def _register_and_login(self, username: str) -> dict[str, str]:
        register_payload = {
            "username": username,
            "email": f"{username}@example.com",
            "password": "StrongPass123!",
        }
        register_response = self.client.post("/api/auth/register/", register_payload, format="json")
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        login_payload = {"username": username, "password": "StrongPass123!"}
        login_response = self.client.post("/api/auth/login/", login_payload, format="json")
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        return {
            "access": login_response.data["access"],
            "refresh": login_response.data["refresh"],
        }

    def test_register_login_refresh_flow(self):
        tokens = self._register_and_login(f"auth_user_{int(time.time())}")
        refresh_response = self.client.post(
            "/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

    def test_logout_blacklists_refresh_token(self):
        username = f"logout_user_{int(time.time())}"
        tokens = self._register_and_login(username)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        logout_response = self.client.post(
            "/api/auth/logout/",
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

        refresh_response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_private_endpoint_requires_authentication(self):
        response = self.client.get("/api/devices/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AccessControlAndFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()

    def _create_user_and_token(self, username: str) -> tuple[object, str]:
        user = self.user_model.objects.create_user(
            username=username, password="StrongPass123!", email=f"{username}@x.com"
        )
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": username, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        return user, login_response.data["access"]

    def test_user_cannot_create_measurement_for_foreign_device(self):
        user_a, token_a = self._create_user_and_token("owner_a")
        _user_b, token_b = self._create_user_and_token("owner_b")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_a}")
        device_response = self.client.post(
            "/api/devices/",
            {
                "device_type": "glucometer",
                "serial": f"foreign-device-{int(time.time())}",
                "protocol": "bluetooth",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(device_response.status_code, status.HTTP_201_CREATED)
        device_id = device_response.data["id"]
        self.assertEqual(Device.objects.get(id=device_id).user_id, user_a.id)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_b}")
        measurement_response = self.client.post(
            "/api/measurements/",
            {
                "device": device_id,
                "parameter_type": "glucose",
                "value": 120.5,
                "unit": "mg/dL",
                "measured_at": "2026-02-25T00:00:00Z",
            },
            format="json",
        )
        self.assertEqual(measurement_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_measurements_filter_works(self):
        _user, token = self._create_user_and_token("filter_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        device_response = self.client.post(
            "/api/devices/",
            {
                "device_type": "glucometer",
                "serial": f"filter-device-{int(time.time())}",
                "protocol": "bluetooth",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(device_response.status_code, status.HTTP_201_CREATED)
        device_id = device_response.data["id"]

        create_measurement = self.client.post(
            "/api/measurements/",
            {
                "device": device_id,
                "parameter_type": "glucose",
                "value": 105.2,
                "unit": "mg/dL",
                "measured_at": "2026-02-24T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(create_measurement.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/measurements/?from=2026-02-20T00:00:00Z&to=2026-02-25T00:00:00Z&device={device_id}&parameter=glucose"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_measurement_creation_generates_recommendation(self):
        user, token = self._create_user_and_token("recommendation_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        device_response = self.client.post(
            "/api/devices/",
            {
                "device_type": "glucometer",
                "serial": f"recommendation-device-{int(time.time())}",
                "protocol": "bluetooth",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(device_response.status_code, status.HTTP_201_CREATED)
        device_id = device_response.data["id"]

        measurement_response = self.client.post(
            "/api/measurements/",
            {
                "device": device_id,
                "parameter_type": "glucose",
                "value": 160.0,
                "unit": "mg/dL",
                "measured_at": "2026-02-24T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(measurement_response.status_code, status.HTTP_201_CREATED)
        measurement_id = measurement_response.data["id"]

        recommendation = Recommendation.objects.get(measurement_id=measurement_id, user_id=user.id)
        self.assertIn(recommendation.engine, {"rules", "ai"})
        self.assertIn(recommendation.level, {"normal", "preventive", "critical"})
        self.assertTrue(recommendation.text)

    def test_measurement_creation_survives_recommendation_failure(self):
        _user, token = self._create_user_and_token("recommendation_failure_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        device_response = self.client.post(
            "/api/devices/",
            {
                "device_type": "glucometer",
                "serial": f"recommendation-failure-device-{int(time.time())}",
                "protocol": "bluetooth",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(device_response.status_code, status.HTTP_201_CREATED)
        device_id = device_response.data["id"]

        with patch(
            "measurements.views.generate_immediate_recommendation",
            side_effect=RuntimeError("engine unavailable"),
        ):
            measurement_response = self.client.post(
                "/api/measurements/",
                {
                    "device": device_id,
                    "parameter_type": "glucose",
                    "value": 140.0,
                    "unit": "mg/dL",
                    "measured_at": "2026-02-24T10:00:00Z",
                },
                format="json",
            )
        self.assertEqual(measurement_response.status_code, status.HTTP_201_CREATED)
