# 🌶️ Unofficial SpicyChat API

An asynchronous, reverse-engineered Python wrapper for the **SpicyChat.ai** API.

> ⚠️ **Disclaimer:**
> This is an **unofficial** library. It is **not affiliated with**, **endorsed**, or **supported** by SpicyChat.ai.
> Use at your own risk — API changes may **break functionality** at any time.

---

## ✨ Features

- 🌀 Fully **asynchronous** — powered by `httpx` + `asyncio`
- 🔐 **Stateful authentication** — supports OTP-based login and session handling
- 💾 **Token persistence** — reuse sessions with ease
- 💬 High-level access to:
  - Messaging
  - User profiles
  - Personas
  - Search
- 🔧 All API quirks abstracted away — just use Pythonic methods
- 📦 **Type-safe** via Pydantic models

---

## 📦 Installation

> Make sure you have **Python 3.8+** installed.

```bash
poetry install
