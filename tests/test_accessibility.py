import re
import unittest
from pathlib import Path


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _luminance(hex_color: str) -> float:
    channels = []
    for value in _rgb(hex_color):
        normalized = value / 255
        channels.append(normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float:
    first, second = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)


class AccessibilityThemeTests(unittest.TestCase):
    def test_all_declared_text_pairs_pass_wcag_aa(self) -> None:
        pairs = {
            "body": ("#1F2937", "#F5F7FA"),
            "muted body": ("#475569", "#FFFFFF"),
            "placeholder": ("#526173", "#FFFFFF"),
            "sidebar": ("#FFFFFF", "#0B2E59"),
            "sidebar hover": ("#FFFFFF", "#163F70"),
            "primary button": ("#FFFFFF", "#0B2E59"),
            "primary button hover": ("#FFFFFF", "#1D4E89"),
            "secondary button": ("#0B2E59", "#FFFFFF"),
            "active navigation": ("#0B2E59", "#FFFFFF"),
            "hero supporting text": ("#DCE9F7", "#0B2E59"),
            "link": ("#164F8C", "#FFFFFF"),
            "alert": ("#12395F", "#E8F1FA"),
        }
        for name, (foreground, background) in pairs.items():
            with self.subTest(name=name):
                self.assertGreaterEqual(contrast_ratio(foreground, background), 4.5)

    def test_css_defines_critical_accessible_states(self) -> None:
        css = Path("ui/styles.py").read_text(encoding="utf-8")
        for selector in ("input::placeholder", "label:has(input:checked)", '[data-testid="stAlert"]', "button:focus-visible"):
            self.assertIn(selector, css)
        self.assertIsNone(re.search(r"stSidebar[^\n]+\]\s+\*\s*\{\s*color:\s*#(?:fff|ffffff)", css, re.IGNORECASE))

    def test_onboarding_summary_is_sticky_but_cards_are_not(self) -> None:
        css = Path("ui/styles.py").read_text(encoding="utf-8")
        self.assertIn(".st-key-onboarding_sticky_summary", css)
        self.assertIn("position: sticky", css)
        self.assertIn("linear-gradient(135deg, #FFF7D6", css)
        self.assertIn("background-color: #F59E0B", css)
        self.assertNotIn(".st-key-onboarding_steps_card {\n          position: sticky", css)
        self.assertIn(".onboarding-title-mobile", css)

    def test_mobile_navigation_auto_collapse_script_is_present(self) -> None:
        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("collapseSidebarOnMobile", app_source)
        self.assertIn('max-width: 768px', app_source)
        self.assertIn('stSidebarCollapseButton', app_source)

    def test_mobile_menu_toggle_is_available_and_not_hidden_with_branding(self) -> None:
        app_source = Path("app.py").read_text(encoding="utf-8")
        css = Path("ui/styles.py").read_text(encoding="utf-8")
        self.assertIn("render_mobile_menu_toggle", app_source)
        self.assertIn("getexpert-mobile-menu-toggle-v4", app_source)
        self.assertIn("getexpert-mobile-sidebar-close-v4", app_source)
        self.assertIn("getexpert-mobile-sidebar-open", app_source)
        self.assertIn("getexpert-mobile-sidebar-closed", app_source)
        self.assertIn('desktopBreakpoint = "(min-width: 769px)"', app_source)
        self.assertIn("☰ เมนู", app_source)
        self.assertIn("<<", app_source)
        self.assertIn("stSidebarCollapsedControl", app_source)
        self.assertIn("stExpandSidebarButton", app_source)
        self.assertIn("stSidebarCollapseButton", app_source)
        self.assertIn("toggleSidebarFromMenu", app_source)
        self.assertIn("closeMobileSidebar", app_source)
        self.assertIn("addEventListener", app_source)
        self.assertIn('"onclick"', app_source)
        self.assertIn("clickedMenu", app_source)
        self.assertIn("clickedClose", app_source)
        self.assertIn("clickedCollapse", app_source)
        self.assertIn("event.stopPropagation", app_source)
        self.assertIn("data-getexpert-menu-toggle", app_source)
        self.assertIn("max-width: 768px", app_source)
        self.assertIn("min-width: 769px", app_source)
        self.assertNotIn("getexpert-mobile-menu-toggle", css)

    def test_sidebar_does_not_render_developer_config_status(self) -> None:
        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertNotIn("safe_debug_message", app_source)
        self.assertNotIn("SUPABASE_URL", app_source)
        self.assertNotIn("SUPABASE_ANON_KEY", app_source)
        self.assertNotIn("Config source", app_source)
        self.assertNotIn("โปรไฟล์พร้อมใช้งาน", app_source)
        self.assertNotIn("supabase_sync_error", app_source)

    def test_dashboard_charts_define_distinct_target_and_actual_colors(self) -> None:
        dashboard_source = Path("views/dashboard_page.py").read_text(encoding="utf-8")
        self.assertIn("ผลลัพธ์จริง", dashboard_source)
        self.assertIn('"domain": ["เป้าหมาย", "ผลลัพธ์จริง"]', dashboard_source)
        self.assertIn('"range": ["#0B2E59", "#F59E0B"]', dashboard_source)

    def test_streamlit_cloud_branding_and_toolbar_are_hidden_globally(self) -> None:
        css = Path("ui/styles.py").read_text(encoding="utf-8")
        for selector in (
            "#MainMenu",
            "footer",
            '[data-testid="stToolbar"]',
            '[data-testid="stHeaderActionElements"]',
            '[data-testid="stStatusWidget"]',
            ".stDeployButton",
            ".stAppDeployButton",
            '[class*="viewerBadge"]',
            '[aria-label*="Streamlit" i]',
            'iframe[src*="streamlit" i]',
            'body > iframe[style*="position: fixed" i]',
            'body > div[style*="position: fixed" i][style*="bottom" i][style*="right" i] iframe',
            ".viewerBadge_container__1QSob",
            'a[href*="streamlit.io/cloud"]',
        ):
            self.assertIn(selector, css)
        self.assertIn("pointer-events: none", css)
        self.assertIn('[data-testid="stSidebarCollapseButton"]', css)


if __name__ == "__main__":
    unittest.main()
