# 📈 AktienAlarmBot mit Telegram & Docker

Ein Bot zur Überwachung von Aktienkursen mit Telegram-Benachrichtigungen.

## 🔧 Startanleitung

### Voraussetzungen

- Docker & Docker Compose

### Starten

```bash
git clone https://github.com/dein-name/AktienBot.git
cd AktienBot
docker-compose up --build -d

In docker-compose.yaml eingeben:

environment:
  TELEGRAM_TOKEN: "dein_token"
  TELEGRAM_CHAT_ID: "123456"
  OPENROUTER_API_KEY: "sk-..."

