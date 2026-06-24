from __future__ import annotations

from pathlib import Path

import streamlit as st

from models import AppUser
from services.subscription_service import (
    effective_subscription_status,
    normalize_subscription_user,
)


LINE_OA_URL = "https://lin.ee/YXNuJrR5"


def render_payment_page(user: AppUser) -> None:
    user = normalize_subscription_user(user)
    st.title("ชำระเงิน / เปิดใช้งาน")
    status = effective_subscription_status(user)
    labels = {
        "pending_payment": "รอชำระเงิน / รออนุมัติ",
        "active": "เปิดใช้งานแล้ว",
        "expired": "หมดอายุ",
        "suspended": "ถูกระงับ",
    }
    st.info(f"สถานะปัจจุบัน: {labels.get(status, status)}")
    st.write(f"แพ็กเกจปัจจุบัน: **{user.subscription_plan or 'Member'}**")
    if user.subscription_expires_at:
        st.write(f"ใช้งานได้ถึง: **{user.subscription_expires_at[:10]}**")
    st.metric("ค่าบริการแพ็กเกจ Member", "89 บาท / เดือน")
    st.write(
        "กรุณาสแกน QR Code เพื่อชำระเงิน 89 บาท หลังจากชำระเงินแล้ว "
        "กรุณาส่งสลิปมาที่ LINE OA เพื่อให้ผู้ดูแลระบบตรวจสอบและเปิดใช้งานบัญชี"
    )
    qr_path = Path(__file__).resolve().parents[1] / "assets" / "payment_qr.png"
    if qr_path.is_file():
        st.image(str(qr_path), caption="QR Code ชำระเงิน Member 89 บาท", width=320)
    else:
        st.warning(
            "ยังไม่ได้ตั้งค่า QR Code กรุณาติดต่อผู้ดูแลระบบหรือแจ้งชำระเงินทาง LINE OA"
        )
    st.markdown(
        f"""
        <style>
        .getexpert-line-payment-cta {{
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          max-width: 420px;
          min-height: 52px;
          margin: 1rem 0 1.25rem;
          padding: 0.75rem 1.25rem;
          border: 2px solid #04A947;
          border-radius: 10px;
          background: #06C755;
          color: #111111 !important;
          font-weight: 800;
          font-size: 1.05rem;
          line-height: 1.3;
          text-align: center;
          text-decoration: none !important;
          box-shadow: 0 5px 16px rgba(6, 199, 85, 0.30);
          transition: transform 160ms ease, background-color 160ms ease,
                      box-shadow 160ms ease;
          animation: getexpert-line-pulse 2.8s ease-in-out infinite;
        }}
        .getexpert-line-payment-cta:hover {{
          background: #05B84E;
          color: #0B1F13 !important;
          transform: translateY(-2px);
          box-shadow: 0 8px 22px rgba(6, 199, 85, 0.42);
        }}
        .getexpert-line-payment-cta:focus-visible {{
          outline: 3px solid #0B2E59;
          outline-offset: 3px;
        }}
        @keyframes getexpert-line-pulse {{
          0%, 100% {{ box-shadow: 0 5px 16px rgba(6, 199, 85, 0.28); }}
          50% {{ box-shadow: 0 6px 24px rgba(6, 199, 85, 0.48); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
          .getexpert-line-payment-cta {{
            animation: none;
            transition: none;
          }}
        }}
        </style>
        <a class="getexpert-line-payment-cta"
           href="{LINE_OA_URL}"
           target="_blank"
           rel="noopener noreferrer">
          แจ้งชำระเงินทาง LINE
        </a>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "หากต้องการใช้งานระดับ Leader หรือ Team Dashboard กรุณาติดต่อผู้ดูแลระบบทาง "
        "LINE OA เพื่อรับรายละเอียดและชำระค่าบริการแพ็กเกจ Leader"
    )
