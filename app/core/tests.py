from __future__ import annotations

import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from devices.models import Device, DeviceProfile
from recommendations.models import PeriodicDiagnostic, Recommendation


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

    def test_register_without_profile_creates_empty_profile(self):
        from users.models import Profile

        username = f"no_profile_{int(time.time())}"
        resp = self.client.post(
            "/api/auth/register/",
            {"username": username, "email": f"{username}@x.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(username=username)
        self.assertTrue(Profile.objects.filter(user=user).exists())
        profile = user.profile
        self.assertIsNone(profile.birth_date)
        self.assertEqual(profile.biological_sex, "")

    def test_register_with_profile_saves_health_data(self):
        from users.models import Profile

        username = f"with_profile_{int(time.time())}"
        resp = self.client.post(
            "/api/auth/register/",
            {
                "username": username,
                "email": f"{username}@x.com",
                "password": "StrongPass123!",
                "profile": {
                    "birth_date": "1990-05-15",
                    "biological_sex": "masculino",
                    "initial_weight_kg": "75.50",
                    "height_cm": "175.0",
                    "activity_level": "moderado",
                    "preexisting_conditions": "Hipertension arterial",
                },
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        profile = get_user_model().objects.get(username=username).profile
        self.assertEqual(str(profile.birth_date), "1990-05-15")
        self.assertEqual(profile.biological_sex, "masculino")
        self.assertEqual(float(profile.initial_weight_kg), 75.50)
        self.assertEqual(float(profile.height_cm), 175.0)
        self.assertEqual(profile.activity_level, "moderado")
        self.assertEqual(profile.preexisting_conditions, "Hipertension arterial")

    def test_private_endpoint_requires_authentication(self):
        response = self.client.get("/api/devices/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_email_works(self):
        username = f"email_login_{int(time.time())}"
        email = f"{username}@example.com"
        password = "StrongPass123!"
        register_response = self.client.post(
            "/api/auth/register/",
            {"username": username, "email": email, "password": password},
            format="json",
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        login_response = self.client.post(
            "/api/auth/login/",
            {"username": email, "password": password},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)

    def test_login_with_duplicate_email_requires_username(self):
        user_model = get_user_model()
        password = "StrongPass123!"
        shared_email = f"dup_{int(time.time())}@example.com"
        user_model.objects.create_user(username=f"user_a_{int(time.time())}", email=shared_email, password=password)
        user_model.objects.create_user(
            username=f"user_b_{int(time.time()) + 1}", email=shared_email, password=password
        )

        login_response = self.client.post(
            "/api/auth/login/",
            {"username": shared_email, "password": password},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", login_response.data)


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
                "device_type": "glucometro",
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
                "device_type": "glucometro",
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
                "device_type": "glucometro",
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
        self.assertIn(recommendation.engine, {"rules", "algorithmic"})
        self.assertIn(recommendation.level, {"normal", "preventive", "critical"})
        self.assertEqual(recommendation.kind, "immediate")
        self.assertEqual(recommendation.device_type, "glucometro")
        self.assertTrue(recommendation.text)

    def test_measurement_creation_survives_recommendation_failure(self):
        _user, token = self._create_user_and_token("recommendation_failure_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        device_response = self.client.post(
            "/api/devices/",
            {
                "device_type": "glucometro",
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


class DeviceProfileTests(APITestCase):
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
        return user, login_response.data["access"]

    def test_device_profiles_requires_auth(self):
        response = self.client.get("/api/device-profiles/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_device_profiles_returns_active_profiles(self):
        DeviceProfile.objects.create(
            name="Test Oximetro",
            device_type="oximetro",
            manufacturer="Yonker",
            model_name="TEST-PROFILE",
            protocol="bluetooth",
            ble_service_uuid="CDEACD80-5235-4C07-8846-93A37EE6B86D",
            ble_characteristic_uuid="CDEACD81-5235-4C07-8846-93A37EE6B86D",
            supported_parameters=["spo2", "pulse_rate", "pi_index", "hrv"],
            is_active=True,
        )
        _user, token = self._create_user_and_token("profile_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/device-profiles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        profile = next(item for item in response.data if item["device_type"] == "oximetro")
        self.assertEqual(profile["device_type"], "oximetro")
        self.assertIn("spo2", profile["supported_parameters"])

    def test_device_profiles_excludes_bascula(self):
        DeviceProfile.objects.create(
            name="Test Bascula",
            device_type="bascula",
            manufacturer="JK",
            model_name="JK-100",
            protocol="bluetooth",
            supported_parameters=["weight"],
            is_active=True,
        )
        _user, token = self._create_user_and_token("profile_exclude_scale")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/device-profiles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item["device_type"] != "bascula" for item in response.data))


class DeviceIsolationTests(APITestCase):
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

    def test_rejects_bascula_device_creation(self):
        _user, token = self._create_user_and_token("scale_blocked")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/api/devices/",
            {
                "device_type": "bascula",
                "serial": f"SCALE-{int(time.time())}",
                "protocol": "bluetooth",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("device_type", response.data)

    def test_list_devices_excludes_bascula(self):
        user, token = self._create_user_and_token("scale_hidden")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        Device.objects.create(
            user=user,
            device_type="bascula",
            serial=f"SCALE-HIDDEN-{int(time.time())}",
            protocol="bluetooth",
            is_active=True,
        )
        Device.objects.create(
            user=user,
            device_type="oximetro",
            serial=f"OX-VISIBLE-{int(time.time())}",
            protocol="bluetooth",
            is_active=True,
        )

        response = self.client.get("/api/devices/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item["device_type"] != "bascula" for item in response.data))
        self.assertTrue(any(item["device_type"] == "oximetro" for item in response.data))


class CrossValidationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()
        cls.profile = DeviceProfile.objects.create(
            name="Cross Oximetro",
            device_type="oximetro",
            manufacturer="Yonker",
            model_name="CROSS-TEST",
            protocol="bluetooth",
            supported_parameters=["spo2", "pulse_rate", "pi_index", "hrv"],
            is_active=True,
        )

    def _create_user_and_token(self, username: str) -> tuple[object, str]:
        user = self.user_model.objects.create_user(
            username=username, password="StrongPass123!", email=f"{username}@x.com"
        )
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": username, "password": "StrongPass123!"},
            format="json",
        )
        return user, login_response.data["access"]

    def _create_oximeter(self, token: str, serial: str) -> int:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.post(
            "/api/devices/",
            {"device_type": "oximetro", "serial": serial, "protocol": "bluetooth", "is_active": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return resp.data["id"]

    def test_cross_validation_rejects_incompatible_param(self):
        _user, token = self._create_user_and_token("cross_reject")
        device_id = self._create_oximeter(token, f"OX-CROSS-REJ-{int(time.time())}")

        resp = self.client.post(
            "/api/measurements/",
            {"device": device_id, "parameter_type": "glucose", "value": 120, "unit": "mg/dL", "measured_at": "2026-02-25T10:00:00Z"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parameter_type", resp.data)

    def test_cross_validation_allows_compatible_param(self):
        _user, token = self._create_user_and_token("cross_allow")
        device_id = self._create_oximeter(token, f"OX-CROSS-OK-{int(time.time())}")

        resp = self.client.post(
            "/api/measurements/",
            {"device": device_id, "parameter_type": "spo2", "value": 96, "unit": "%", "measured_at": "2026-02-25T10:00:00Z"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


class MeasurementBatchTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()
        cls.profile = DeviceProfile.objects.create(
            name="Batch Oximetro",
            device_type="oximetro",
            manufacturer="Yonker",
            model_name="BATCH-TEST",
            protocol="bluetooth",
            supported_parameters=["spo2", "pulse_rate", "pi_index", "hrv"],
            is_active=True,
        )

    def _create_user_and_token(self, username: str) -> tuple[object, str]:
        user = self.user_model.objects.create_user(
            username=username, password="StrongPass123!", email=f"{username}@x.com"
        )
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": username, "password": "StrongPass123!"},
            format="json",
        )
        return user, login_response.data["access"]

    def _create_oximeter(self, token: str, serial: str) -> int:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.post(
            "/api/devices/",
            {"device_type": "oximetro", "serial": serial, "protocol": "bluetooth", "is_active": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return resp.data["id"]

    def test_batch_requires_auth(self):
        response = self.client.post("/api/measurements/batch/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_batch_creates_measurements_and_recommendations(self):
        user, token = self._create_user_and_token("batch_ok")
        device_id = self._create_oximeter(token, f"OX-BATCH-OK-{int(time.time())}")

        resp = self.client.post(
            "/api/measurements/batch/",
            {
                "device": device_id,
                "measured_at": "2026-02-25T10:30:00Z",
                "readings": [
                    {"parameter_type": "spo2", "value": "96", "unit": "%"},
                    {"parameter_type": "pulse_rate", "value": "72", "unit": "bpm"},
                    {"parameter_type": "pi_index", "value": "3.5", "unit": "%"},
                    {"parameter_type": "hrv", "value": "45", "unit": "ms"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data), 4)

        recs = Recommendation.objects.filter(user=user)
        self.assertEqual(recs.count(), 4)

    def test_batch_rejects_incompatible_param(self):
        user, token = self._create_user_and_token("batch_rej")
        device_id = self._create_oximeter(token, f"OX-BATCH-REJ-{int(time.time())}")

        resp = self.client.post(
            "/api/measurements/batch/",
            {
                "device": device_id,
                "measured_at": "2026-02-25T10:30:00Z",
                "readings": [
                    {"parameter_type": "spo2", "value": "96", "unit": "%"},
                    {"parameter_type": "glucose", "value": "120", "unit": "mg/dL"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        from measurements.models import Measurement
        self.assertEqual(Measurement.objects.filter(user=user).count(), 0)


class PhysiologicalRangeValidationTests(APITestCase):
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
        return user, login_response.data["access"]

    def _create_device(self, token: str, serial: str, device_type: str = "glucometro") -> int:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.post(
            "/api/devices/",
            {"device_type": device_type, "serial": serial, "protocol": "bluetooth", "is_active": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return resp.data["id"]

    def test_spo2_zero_rejected(self):
        _user, token = self._create_user_and_token("physio_spo2")
        device_id = self._create_device(token, f"PHY-SPO2-{int(time.time())}", "oximetro")
        resp = self.client.post(
            "/api/measurements/",
            {"device": device_id, "parameter_type": "spo2", "value": "0", "unit": "%", "measured_at": "2026-02-25T10:00:00Z"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pulse_rate_zero_rejected(self):
        _user, token = self._create_user_and_token("physio_pr")
        device_id = self._create_device(token, f"PHY-PR-{int(time.time())}", "oximetro")
        resp = self.client.post(
            "/api/measurements/",
            {"device": device_id, "parameter_type": "pulse_rate", "value": "0", "unit": "bpm", "measured_at": "2026-02-25T10:00:00Z"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pi_index_zero_rejected(self):
        _user, token = self._create_user_and_token("physio_pi")
        device_id = self._create_device(token, f"PHY-PI-{int(time.time())}", "oximetro")
        resp = self.client.post(
            "/api/measurements/",
            {"device": device_id, "parameter_type": "pi_index", "value": "0", "unit": "%", "measured_at": "2026-02-25T10:00:00Z"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_spo2_accepted(self):
        _user, token = self._create_user_and_token("physio_ok")
        device_id = self._create_device(token, f"PHY-OK-{int(time.time())}", "oximetro")
        resp = self.client.post(
            "/api/measurements/",
            {"device": device_id, "parameter_type": "spo2", "value": "96", "unit": "%", "measured_at": "2026-02-25T10:00:00Z"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_batch_rejects_out_of_range_value(self):
        DeviceProfile.objects.get_or_create(
            model_name="PHYSIO-BATCH-TEST",
            defaults={
                "name": "Physio Batch Oximetro",
                "device_type": "oximetro",
                "manufacturer": "Test",
                "protocol": "bluetooth",
                "supported_parameters": ["spo2", "pulse_rate", "pi_index", "hrv"],
                "is_active": True,
            },
        )
        _user, token = self._create_user_and_token("physio_batch")
        device_id = self._create_device(token, f"PHY-BATCH-{int(time.time())}", "oximetro")
        resp = self.client.post(
            "/api/measurements/batch/",
            {
                "device": device_id,
                "measured_at": "2026-02-25T10:30:00Z",
                "readings": [
                    {"parameter_type": "spo2", "value": "96", "unit": "%"},
                    {"parameter_type": "pulse_rate", "value": "0", "unit": "bpm"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class WeeklyDiagnosticApiTests(APITestCase):
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

    def test_weekly_diagnostics_endpoint_returns_user_results(self):
        user, token = self._create_user_and_token("weekly_diag_user")
        PeriodicDiagnostic.objects.create(
            user=user,
            device_type="glucometro",
            period_start="2026-06-01",
            period_end="2026-06-07",
            frequency="weekly",
            level="preventive",
            summary="Resumen de prueba",
            recommended_action="Accion de prueba",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/diagnostics/weekly/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["device_type"], "glucometro")
