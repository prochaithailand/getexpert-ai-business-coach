from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


PIPELINE_STEPS = (
    ("STEP 1", "🧠 วิเคราะห์คำถามของคุณ", "AI กำลังทำความเข้าใจเป้าหมายและบริบทของธุรกิจ"),
    (
        "STEP 2",
        "📚 ค้นหาความรู้จากคลัง GetExpert",
        "กำลังเชื่อมโยง 5 Modules of MLM, Workplan, CRM และแผนปฏิบัติการ 30 วัน",
    ),
    (
        "STEP 3",
        "📈 วิเคราะห์กลยุทธ์ที่เกี่ยวข้อง",
        "AI กำลังเปรียบเทียบกลยุทธ์และประเมินความเหมาะสม",
    ),
    (
        "STEP 4",
        "🎯 สร้างคำแนะนำเฉพาะสำหรับคุณ",
        "กำลังเรียบเรียงคำตอบให้เหมาะกับสถานการณ์ของคุณ",
    ),
    (
        "STEP 5",
        "✅ ตรวจสอบคุณภาพคำตอบ",
        "ตรวจสอบความครบถ้วน ความสอดคล้อง และการนำไปใช้จริง",
    ),
    ("STEP 6", "🎉 พร้อมแล้ว", "เตรียมแสดงคำตอบจาก AI Business Coach"),
)

THINKING_MESSAGES = (
    "💡 AI กำลังเปรียบเทียบหลายแนวทาง",
    "📊 กำลังประเมินผลกระทบต่อยอดขาย",
    "👥 กำลังวิเคราะห์มุมมองของผู้นำทีม",
    "📈 กำลังจัดลำดับความสำคัญของกลยุทธ์",
    "🎯 กำลังค้นหาแนวทางที่เหมาะกับเป้าหมายของคุณ",
    "📚 กำลังเชื่อมโยงองค์ความรู้จากคลัง GetExpert",
)


@contextmanager
def render_ai_coaching_pipeline() -> Iterator[None]:
    """แสดง UX ระหว่างรอ AI โดยไม่เพิ่มหรือเปลี่ยน OpenAI call."""
    placeholder = st.empty()
    placeholder.markdown(_pipeline_html(), unsafe_allow_html=True)
    try:
        yield
    finally:
        placeholder.empty()


def _pipeline_html() -> str:
    steps = "".join(
        (
            f'<div class="ai-pipeline-step ai-pipeline-step-{index}">'
            f'<span class="ai-step-number">{step}</span>'
            f"<strong>{title}</strong><small>{description}</small></div>"
        )
        for index, (step, title, description) in enumerate(PIPELINE_STEPS, start=1)
    )
    messages = "".join(
        f'<span class="ai-thinking-message ai-thinking-message-{index}">{message}</span>'
        for index, message in enumerate(THINKING_MESSAGES, start=1)
    )
    delays = "".join(
        f".ai-pipeline-step-{index}, .ai-thinking-message-{index} "
        f"{{ animation-delay: {(index - 1) * 3}s; }}"
        for index in range(1, 7)
    )
    return f"""
    <style>
      .ai-pipeline {{
        background: linear-gradient(145deg, #0B2E59, #123f73);
        border: 1px solid #8fa8c2;
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(11, 46, 89, .18);
        color: #FFFFFF;
        padding: 18px;
        margin: 8px 0 16px;
      }}
      .ai-pipeline-title {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 14px; }}
      .ai-pipeline-step {{
        display: none;
        min-height: 72px;
        animation: aiStepCycle 18s infinite;
      }}
      .ai-pipeline-step strong, .ai-pipeline-step small {{ display: block; }}
      .ai-pipeline-step small {{ color: #E5EDF5; margin-top: 5px; line-height: 1.45; }}
      .ai-step-number {{
        color: #BFD2E5;
        display: block;
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .08em;
        margin-bottom: 4px;
      }}
      .ai-thinking {{ color: #FFFFFF; min-height: 24px; position: relative; }}
      .ai-thinking-message {{
        animation: aiMessageCycle 18s infinite;
        opacity: 0;
        position: absolute;
        inset: 0 auto auto 0;
      }}
      {delays}
      @keyframes aiStepCycle {{
        0%, 15% {{ display: block; opacity: 1; transform: translateY(0); }}
        16%, 100% {{ display: none; opacity: 0; transform: translateY(4px); }}
      }}
      @keyframes aiMessageCycle {{
        0%, 15% {{ opacity: 1; }}
        16%, 100% {{ opacity: 0; }}
      }}
      @media (max-width: 640px) {{
        .ai-pipeline {{ padding: 14px; }}
        .ai-pipeline-title {{ font-size: .98rem; }}
      }}
      @media (prefers-reduced-motion: reduce) {{
        .ai-pipeline-step, .ai-thinking-message {{ animation: none; }}
        .ai-pipeline-step-1 {{ display: block; }}
        .ai-thinking-message-1 {{ opacity: 1; }}
      }}
    </style>
    <div class="ai-pipeline" role="status" aria-live="polite">
      <div class="ai-pipeline-title">AI Business Coach กำลังวิเคราะห์ธุรกิจของคุณ...</div>
      <div class="ai-pipeline-steps">{steps}</div>
      <div class="ai-thinking">{messages}</div>
    </div>
    """
