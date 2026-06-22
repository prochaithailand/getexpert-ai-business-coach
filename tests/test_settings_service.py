import unittest

from services.settings_service import load_supabase_config


class SupabaseConfigTests(unittest.TestCase):
    def test_streamlit_secrets_have_priority(self) -> None:
        config = load_supabase_config(
            {"SUPABASE_URL": "https://secrets.supabase.co", "SUPABASE_ANON_KEY": "secret-key"},
            {"SUPABASE_URL": "https://env.supabase.co", "SUPABASE_ANON_KEY": "env-key"},
        )

        self.assertTrue(config.is_complete)
        self.assertEqual(config.url, "https://secrets.supabase.co")
        self.assertEqual(config.anon_key, "secret-key")
        self.assertEqual(config.source, "Streamlit Secrets")
        self.assertNotIn("secret-key", config.safe_debug_message)
        self.assertEqual(
            config.safe_debug_message,
            "SUPABASE_URL: FOUND | SUPABASE_ANON_KEY: FOUND | Config source: Streamlit Secrets",
        )

    def test_environment_is_used_when_secret_pair_is_missing(self) -> None:
        config = load_supabase_config(
            {},
            {"SUPABASE_URL": "https://env.supabase.co", "SUPABASE_ANON_KEY": "env-key"},
        )

        self.assertTrue(config.is_complete)
        self.assertEqual(config.source, "Environment Variables")
        self.assertEqual(config.url, "https://env.supabase.co")
        self.assertEqual(config.anon_key, "env-key")

    def test_missing_config_uses_in_memory_fallback(self) -> None:
        config = load_supabase_config({}, {})

        self.assertFalse(config.is_complete)
        self.assertEqual(config.source, "None")
        self.assertEqual(
            config.safe_debug_message,
            "SUPABASE_URL: NOT FOUND | SUPABASE_ANON_KEY: NOT FOUND | Config source: None",
        )


if __name__ == "__main__":
    unittest.main()
