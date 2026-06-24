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
    st.link_button("แจ้งชำระเงินทาง LINE", LINE_OA_URL, type="primary")
    st.info(
        "หากต้องการใช้งานระดับ Leader หรือ Team Dashboard กรุณาติดต่อผู้ดูแลระบบทาง "
        "LINE OA เพื่อรับรายละเอียดและชำระค่าบริการแพ็กเกจ Leader"
    )
