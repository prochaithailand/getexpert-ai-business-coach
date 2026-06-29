import streamlit as st


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          color-scheme: light;
          --navy: #0B2E59;
          --blue: #1D4E89;
          --white: #FFFFFF;
          --silver: #D7DEE8;
          --light-gray: #F5F7FA;
          --text-dark: #1F2937;
          --text-muted: #475569;
          --focus: #F4C95D;
        }

        /* Global canvas and typography */
        .stApp, [data-testid="stAppViewContainer"] {
          background: var(--light-gray);
          color: var(--text-dark);
        }
        .stApp p, .stApp li, .stApp label, .stApp small,
        [data-testid="stMarkdownContainer"] { color: var(--text-dark); }
        .block-container { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 3rem; }
        h1, h2, h3, h4, h5, h6 { color: var(--navy) !important; letter-spacing: -0.02em; }
        a { color: #164F8C; text-decoration-thickness: 2px; }
        a:hover { color: var(--navy); }
        hr { border-color: #C7D0DC !important; }

        /* Hide Streamlit Cloud chrome for end users */
        #MainMenu,
        footer,
        [data-testid="stToolbar"],
        [data-testid="stHeaderActionElements"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        [data-testid="manage-app-button"],
        [data-testid*="stCloud"],
        [data-testid*="viewerBadge"],
        [data-testid*="ViewerBadge"],
        .stDeployButton,
        .stAppDeployButton,
        .viewerBadge_container__1QSob,
        .viewerBadge_link__1S137,
        [class*="viewerBadge"],
        [class*="ViewerBadge"],
        [class*="stDeployButton"],
        [class*="stAppDeployButton"],
        [class*="streamlit-cloud"],
        [class*="StreamlitCloud"],
        [aria-label*="Streamlit" i],
        [aria-label*="streamlit" i],
        [title*="Streamlit" i],
        [title*="streamlit" i],
        a[href*="streamlit.io/cloud"],
        a[href*="share.streamlit.io"],
        a[href*="github.com/streamlit"],
        iframe[src*="streamlit" i],
        iframe[src*="share.streamlit" i],
        iframe[src*="streamlit.io" i],
        button[class*="streamlit" i],
        button[class*="viewerBadge" i],
        body > iframe[style*="position: fixed" i],
        body > iframe[style*="bottom" i][style*="right" i],
        body > div[style*="position: fixed" i][style*="bottom" i][style*="right" i][class*="streamlit" i],
        body > div[style*="position: fixed" i][style*="bottom" i][style*="right" i][class*="badge" i],
        body > div[style*="position: fixed" i][style*="bottom" i][style*="right" i] iframe,
        body > div[style*="position: fixed" i][style*="bottom" i][style*="right" i] button[aria-label*="Streamlit" i],
        body > div[style*="position: fixed" i][style*="bottom" i][style*="right" i] a[href*="streamlit" i] {
          display: none !important;
          visibility: hidden !important;
          height: 0 !important;
          width: 0 !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }
        header [data-testid="stToolbar"],
        header [data-testid="stHeaderActionElements"] {
          display: none !important;
        }
        [data-testid="stHeader"] {
          background: transparent !important;
          height: 0 !important;
        }

        /* Sidebar and navigation */
        [data-testid="stSidebar"] {
          background: var(--navy);
          border-right: 1px solid #31557F;
        }
        [data-testid="stSidebar"] > div { background: var(--navy); }
        [data-testid="stSidebar"] .brand-name,
        [data-testid="stSidebar"] .brand-tagline,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
          color: var(--white) !important;
        }
        .brand-block { display: flex; gap: 0.8rem; align-items: center; padding: 0.6rem 0 1.5rem; }
        .brand-mark {
          width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center;
          color: var(--navy) !important; font-weight: 800; background: var(--white);
          border: 2px solid #C8D7E8;
        }
        .brand-name { font-weight: 750; line-height: 1.2; }
        .brand-tagline { font-size: 0.75rem; opacity: 1; padding-top: 0.2rem; }
        .brand-powered {
          color: #DCE9F7 !important;
          font-size: 0.68rem;
          font-weight: 700;
          letter-spacing: .04em;
          padding-top: .12rem;
          text-transform: uppercase;
        }
        .sidebar-spacer { height: 1.2rem; }
        [data-testid="stSidebar"] [role="radiogroup"] { gap: 0.35rem; }
        [data-testid="stSidebar"] [role="radiogroup"] label {
          background: transparent;
          border: 1px solid transparent;
          border-radius: 10px;
          padding: 0.55rem 0.7rem;
          white-space: normal;
          min-height: 2.8rem;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label p,
        [data-testid="stSidebar"] [role="radiogroup"] label span {
          color: var(--white) !important;
          font-weight: 650;
          white-space: normal !important;
          overflow-wrap: anywhere;
          line-height: 1.25;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] * {
          white-space: normal !important;
          overflow-wrap: anywhere;
        }
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] * {
          color: var(--white) !important;
          font-weight: 750;
          white-space: normal !important;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
          background: #163F70;
          border-color: #6F8FB2;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
          background: var(--white);
          border-color: var(--white);
          box-shadow: 0 3px 12px rgba(0, 0, 0, 0.18);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span {
          color: var(--navy) !important;
          font-weight: 800;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] {
          background: var(--white) !important;
          border: 1px solid #B8C9DC;
        }
        [data-testid="stSidebar"] [data-testid="stAlert"] * { color: var(--navy) !important; }
        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stSidebarCollapseButton"] button * { color: var(--white) !important; fill: var(--white) !important; }
        [data-testid="stSidebarCollapsedControl"] button,
        [data-testid="stSidebarCollapsedControl"] button * { color: var(--navy) !important; fill: var(--navy) !important; }

        /* Hero and cards */
        .hero {
          background: var(--navy); border-radius: 24px; padding: 3.2rem;
          color: var(--white); position: relative; overflow: hidden;
          box-shadow: 0 18px 50px rgba(11, 46, 89, 0.20);
        }
        .hero:after {
          content: ''; position: absolute; width: 280px; height: 280px; right: -70px; top: -110px;
          border: 1px solid rgba(255,255,255,.25); border-radius: 50%;
          box-shadow: 0 0 0 42px rgba(255,255,255,.06);
        }
        .hero-kicker { color: #DCE9F7; font-size: .8rem; letter-spacing: .12em; font-weight: 750; }
        .hero h1 { color: var(--white) !important; margin: .55rem 0 .3rem; font-size: clamp(2.2rem, 5vw, 4.2rem); max-width: 800px; }
        .hero-powered { color: #DCE9F7; font-weight: 800; margin-bottom: .7rem; letter-spacing: .08em; text-transform: uppercase; }
        .hero p { color: var(--white) !important; font-size: 1.15rem; max-width: 700px; }
        .section-lead { color: var(--text-muted) !important; margin-top: -.45rem; margin-bottom: 1.8rem; }
        .feature-card, .metric-card {
          background: var(--white); border: 1px solid #C7D0DC; border-radius: 18px; padding: 1.35rem;
          min-height: 150px; box-shadow: 0 8px 24px rgba(11, 46, 89, 0.07);
        }
        .feature-number { color: var(--blue); font-weight: 800; font-size: .78rem; letter-spacing: .12em; }
        .feature-card h3 { color: var(--navy) !important; font-size: 1.12rem; margin: .65rem 0 .45rem; }
        .feature-card p { color: var(--text-muted) !important; font-size: .92rem; }
        .st-key-onboarding_sticky_summary {
          position: sticky; top: .6rem; z-index: 900;
          background: linear-gradient(135deg, #FFF7D6 0%, #FFE8A3 100%);
          border: 2px solid #F59E0B;
          border-radius: 16px; padding: .85rem 1rem .7rem;
          box-shadow: 0 12px 30px rgba(146, 64, 14, .22);
          backdrop-filter: blur(8px);
        }
        .onboarding-title {
          color: var(--navy); font-size: 1.45rem; font-weight: 800; margin-bottom: .35rem;
        }
        .onboarding-title-mobile { display: none; }
        .st-key-onboarding_sticky_summary [data-testid="stProgress"] { margin-bottom: 0; }
        .st-key-onboarding_sticky_summary [data-testid="stProgress"] > div > div > div > div {
          background-color: #F59E0B !important;
        }
        .st-key-onboarding_sticky_summary [data-testid="stProgress"] p {
          color: #78350F !important;
          font-weight: 800;
        }
        .st-key-onboarding_steps_card { margin-top: .75rem; }
        .onboarding-step {
          background: var(--white); border: 1px solid #C7D0DC; border-radius: 14px;
          padding: 1rem; min-height: 185px; margin-top: .75rem;
        }
        .onboarding-step.is-complete { border-top: 5px solid var(--blue); }
        .onboarding-step.is-pending { border-top: 5px solid #8B99AA; }
        .onboarding-step-title { color: var(--navy); font-weight: 800; line-height: 1.45; }
        .onboarding-step-title span { color: var(--blue); font-size: 1.15rem; }
        .onboarding-step p { color: var(--text-muted) !important; font-size: .88rem; margin-top: .6rem; }
        .metric-card { min-height: 105px; }
        .metric-label { color: var(--text-muted); font-size: .78rem; font-weight: 650; letter-spacing: .04em; }
        .metric-value { color: var(--navy); font-size: 1.6rem; font-weight: 800; padding-top: .35rem; }
        .plan-day {
          background: var(--white); color: var(--text-dark); border: 1px solid #C7D0DC;
          border-left: 5px solid var(--blue); border-radius: 12px; padding: .8rem 1rem; margin-bottom: .55rem;
        }
        .plan-day strong { color: var(--navy); }
        .plan-day small, .plan-day b { color: var(--text-dark); }

        /* Inputs, selects, and placeholders */
        [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
          background: var(--white) !important;
          color: var(--text-dark) !important;
          border-color: #8291A5 !important;
        }
        input, textarea, [data-baseweb="select"] input {
          color: var(--text-dark) !important;
          caret-color: var(--navy) !important;
        }
        input::placeholder, textarea::placeholder {
          color: #526173 !important;
          opacity: 1 !important;
        }
        [data-baseweb="select"] span, [data-baseweb="select"] svg { color: var(--text-dark) !important; }
        [role="listbox"], [role="option"] { background: var(--white) !important; color: var(--text-dark) !important; }
        [role="option"]:hover, [aria-selected="true"][role="option"] { background: #E4EDF7 !important; color: var(--navy) !important; }
        [data-testid="stNumberInput"] button { background: #E8EDF3 !important; color: var(--navy) !important; }
        [data-testid="stNumberInput"] button svg { fill: var(--navy) !important; }
        [data-testid="stTextInputRootElement"]:focus-within,
        [data-baseweb="textarea"]:focus-within,
        [data-baseweb="select"] > div:focus-within { outline: 3px solid var(--focus); outline-offset: 1px; }

        /* Buttons */
        .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
          background: var(--white); color: var(--navy) !important; border: 2px solid var(--blue);
          border-radius: 10px; font-weight: 750; min-height: 2.65rem;
        }
        .stButton > button *, .stDownloadButton > button *,
        [data-testid="stFormSubmitButton"] button * { color: inherit !important; }
        .stButton > button:hover, .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
          background: #E4EDF7; color: var(--navy) !important; border-color: var(--navy);
        }
        .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
          background: var(--navy); color: var(--white) !important; border-color: var(--navy);
        }
        .stButton > button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
          background: var(--blue); color: var(--white) !important; border-color: var(--blue);
        }
        button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 3px solid var(--focus) !important; outline-offset: 2px; }

        /* Alerts, status, tabs, and chat */
        [data-testid="stAlert"] {
          background: #E8F1FA !important;
          border: 1px solid #8AA8C7 !important;
        }
        [data-testid="stAlert"] * { color: #12395F !important; }
        [data-baseweb="tab-list"] { background: var(--white); border-bottom: 1px solid #B7C2CF; }
        [data-baseweb="tab"] { color: var(--text-dark) !important; }
        [data-baseweb="tab"] p { color: inherit !important; font-weight: 650; }
        [data-baseweb="tab"][aria-selected="true"] { color: var(--navy) !important; background: #E4EDF7; }
        [data-testid="stChatMessage"] {
          background: var(--white); color: var(--text-dark); border: 1px solid #C7D0DC;
          border-radius: 14px; padding: .35rem .8rem;
        }
        [data-testid="stChatMessage"] * { color: var(--text-dark); }
        [data-testid="stChatInput"] { background: var(--white); border: 1px solid #8291A5; }
        [data-testid="stChatInput"] textarea { background: var(--white) !important; color: var(--text-dark) !important; }
        [data-testid="stChatInputSubmitButton"] { background: var(--navy) !important; color: var(--white) !important; }
        [data-testid="stChatInputSubmitButton"] svg { fill: var(--white) !important; }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--text-muted) !important; }

        @media (max-width: 700px) {
          .hero { padding: 2rem 1.4rem; }
          .block-container { padding-top: 1.2rem; }
          .st-key-onboarding_sticky_summary {
            top: .35rem; border-radius: 12px; padding: .5rem .7rem .4rem;
            box-shadow: 0 7px 18px rgba(11, 46, 89, .15);
          }
          .onboarding-title { font-size: 1rem; line-height: 1.2; margin-bottom: .15rem; }
          .onboarding-title-desktop { display: none; }
          .onboarding-title-mobile { display: inline; }
          .st-key-onboarding_sticky_summary [data-testid="stProgress"] p { font-size: .78rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
