# 📈 AktienAlarmBot – Telegram Aktien-Kursüberwachung

**DE | EN below**

Ein einfacher Python-Bot zur Überwachung von Aktienkursen mit Benachrichtigungen über Telegram. Unterstützt dynamische Kursgrenzen (z. B. -1.5 %) und viele bekannte Aktien (DAX, NASDAQ, MidCaps etc.). Ideal zur schnellen Erkennung von Kursbewegungen.

---

## ⚙️ Funktionen

- 📉 Kursveränderungen automatisch melden
- 📲 Telegram-Benachrichtigung mit Symbol, Prozent und Schwelle
- 💾 Konfigurierbar über `aktien_liste.json`
- 🔄 Dynamische Schwellenwerte per Telegram-Befehl änderbar
- 🐳 Docker-kompatibel (für VPS / Homeserver)

---

## 🚀 Schnellstart mit Docker

### Voraussetzungen

- Docker & Docker Compose
- Telegram-Bot mit Token und Chat-ID ([Anleitung hier](https://core.telegram.org/bots))

### 1. Klone das Projekt

```bash
git clone https://github.com/Fraeser-1E61/aktienalarmbot.git
cd aktienalarmbot

docker-compose up --build -d


Öffne aktien_liste.json und ändere z. B.:

{
  "AAPL": -0.015,
  "SAP.DE": -0.01,
  "NVDA": -0.02
}


