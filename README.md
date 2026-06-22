# GetExpert AI Business Coach V2

A modular Streamlit application for direct selling and network marketing member success.

## Run locally

```powershell
cd "C:\Users\prame\Documents\MASHARE MASS\getexpert_ai_business_coach"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

This workspace already includes an isolated environment with the dependency installed, so it can also be launched directly:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## What is included

- Professional navy-and-white responsive interface
- Member profile stored in the current Streamlit session
- Personalized 30-day action plan
- Facebook, TikTok, and LINE OA draft generators
- Context-aware coaching chat with conversation history
- Thai AI Knowledge Coach that retrieves answers from local PDF sources first
- OpenAI Responses API coaching with member-profile and chat-history context
- Searchable PDF knowledge base with categories and in-app document viewing
- Service contracts ready for OpenAI and Supabase implementations

## ระบบเข้าสู่ระบบต้นแบบ

ระบบบัญชีผู้ใช้ต้นแบบเก็บข้อมูลไว้ในหน่วยความจำของ Streamlit และเก็บผู้ใช้ที่ล็อกอินใน session state บัญชีที่สมัครใหม่จะได้รับบทบาทสมาชิกเสมอ

กำหนดบัญชีผู้ดูแลระบบเริ่มต้นผ่าน environment variables หรือ `.streamlit/secrets.toml`:

```toml
PROTOTYPE_ADMIN_EMAIL = "owner@example.com"
PROTOTYPE_ADMIN_PASSWORD = "รหัสผ่านอย่างน้อย 8 ตัวอักษร"
PROTOTYPE_ADMIN_NAME = "ชื่อผู้ดูแลระบบ"
```

ผู้ดูแลระบบสามารถเลื่อนสมาชิกเป็นผู้นำ และเลื่อนผู้นำเป็นผู้ดูแลระบบได้จากเมนู `จัดการผู้ใช้` ข้อมูลต้นแบบจะหายเมื่อ session หรือ process ถูกรีเซ็ต ควรย้ายไปใช้ Supabase Auth และฐานข้อมูลก่อนใช้งานจริง

## Integration path

Implement the `CoachService` protocol in `services/coach_service.py` to connect an OpenAI client. Implement the `ProfileRepository` protocol in `services/profile_repository.py` to persist profiles in Supabase. The page layer does not need to change when those adapters are introduced.

Generated content is a draft and should be reviewed against local direct-selling regulations, product claims policy, and company compliance rules before use.

## Knowledge base

Place PDF files in the `knowledge/` folder. Subfolder names are used as categories; PDFs placed directly in `knowledge/` are categorized automatically from their filenames. Documents become available after the app refreshes.

The AI Knowledge Coach extracts and searches PDF text locally. Answers are grounded in matching passages and show only friendly source document names, never local file paths. When the retrieved evidence is insufficient, the coach says so instead of generating an unsupported answer.

## OpenAI configuration

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` and `OPENAI_EMBEDDING_MODEL` as environment variables, or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add the key there. Never commit the real secrets file. With a key, the coach uses semantic retrieval through OpenAI embeddings and caches the resulting index locally. Without a key, the app remains usable with lexical retrieval and the local knowledge-coach fallback.

## Supabase persistence

กำหนดค่าต่อไปนี้ใน `.streamlit/secrets.toml` หรือ environment variables:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

ติดตั้ง schema ด้วยไฟล์ `supabase/migrations/20260621_getexpert_schema.sql` ผ่าน Supabase SQL Editor หรือระบบ migration ของ Supabase ก่อนเปิดใช้งาน Data API แอปจะตรวจตารางทั้ง 9 รายการอัตโนมัติและแจ้งเตือนเป็นภาษาไทยหากยังติดตั้งไม่ครบ

`SUPABASE_ANON_KEY` ไม่ได้รับสิทธิ์สร้างตารางฐานข้อมูลโดยตรง การสร้าง schema อัตโนมัติจากคีย์นี้จึงไม่ปลอดภัยและไม่สามารถทำได้โดย Data API หลังรัน migration แล้ว การสมัครสมาชิกจะสร้างบัญชีใน Supabase Auth และสร้างแถว `users` บทบาท Member ผ่าน database trigger

สำหรับ Admin คนแรก ให้สมัครบัญชีตามปกติแล้วใช้ SQL Editor ของเจ้าของระบบเพียงครั้งเดียว:

```sql
update public.users set role = 'Admin' where email = 'owner@example.com';
```

หลังจากนั้น Admin สามารถเลื่อน Member เป็น Leader และ Leader เป็น Admin จากหน้า `จัดการผู้ใช้` ได้ ข้อมูลโปรไฟล์ ทีม CRM, Workplan, แผน 30 วัน, PP, ประวัติคอนเทนต์ และแชต AI จะถูกโหลดกลับทุกครั้งหลังเข้าสู่ระบบ
