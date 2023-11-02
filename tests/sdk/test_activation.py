import unittest

from dynatrace_extension import ActivationConfig, ActivationType


class TestActivation(unittest.TestCase):
    def test_remote_activation(self):
        raw_activation = {
            "enabled": True,
            "description": "RabbitMQ Monitoring",
            "version": "1.0.10",
            "pythonRemote": {"endpoints": [{"url": "http://127.0.0.1:15672", "user": "guest", "password": "guest"}]},
        }
        activation = ActivationConfig(raw_activation)

        self.assertTrue(activation.enabled)
        self.assertEqual(activation.description, "RabbitMQ Monitoring")
        self.assertEqual(activation.version, "1.0.10")
        self.assertEqual(activation.type, ActivationType.REMOTE)
        self.assertEqual(activation["endpoints"][0]["url"], "http://127.0.0.1:15672")
        self.assertEqual(activation.remote["endpoints"][0]["url"], "http://127.0.0.1:15672")
        self.assertFalse(activation.local)

    def test_local_activation(self):
        raw_activation = {
            "enabled": False,
            "description": "RabbitMQ Monitoring",
            "version": "1.0.10",
            "pythonLocal": {"url": "http://127.0.0.1:15672", "user": "guest", "password": "guest"},
        }
        activation = ActivationConfig(raw_activation)

        self.assertFalse(activation.enabled)
        self.assertEqual(activation.description, "RabbitMQ Monitoring")
        self.assertEqual(activation.version, "1.0.10")
        self.assertEqual(activation.type, ActivationType.LOCAL)
        self.assertEqual(activation["url"], "http://127.0.0.1:15672")
        self.assertEqual(activation.local["url"], "http://127.0.0.1:15672")
        self.assertFalse(activation.remote)

    def test_bad_key(self):
        raw_activation = {
            "enabled": False,
            "description": "RabbitMQ Monitoring",
            "version": "1.0.10",
            "pythonLocal": {"url": "http://127.0.0.1:15672", "user": "guest", "password": "guest"},
        }
        activation = ActivationConfig(raw_activation)

        with self.assertRaises(KeyError):
            _ = activation["bad_key"]

    def test_direct_access_versus_get(self):
        raw_activation = {
            "enabled": False,
            "description": "RabbitMQ Monitoring",
            "version": "1.0.10",
            "pythonLocal": {"url": "http://127.0.0.1:15672", "user": "guest", "password": "guest"},
        }
        activation = ActivationConfig(raw_activation)
        assert activation["url"] == activation.get("url", "")
