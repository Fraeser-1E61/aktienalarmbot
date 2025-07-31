import logging
import asyncio
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import yfinance as yf
from datetime import datetime
from openai import OpenAI



import os
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
DEINE_CHAT_ID = int(os.environ["DEINE_CHAT_ID"])
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

# --- EINSTELLUNGEN ---

# --- KI-INTEGRATION MIT OPENROUTER ---


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def ki_analyse_fuer_aktie(symbol, delta, aktueller_preis, waehrung, firmenname):
    """
    Fragt Qwen3 nach möglichen Gründen für die Kursbewegung.
    Gibt eine kurze, sachliche Analyse zurück.
    """
    try:
        prompt = f"""
        Der Kurs von {firmenname} ({symbol}) ist um {delta:+.2f}% {'gefallen' if delta < 0 else 'gestiegen'}.
        Aktueller Kurs: {aktueller_preis} {waehrung}.
        Nenne 2–3 mögliche Gründe für diese Bewegung – basierend auf typischen Marktfaktoren:
        - Sektorweite Korrektur?
        - Unternehmensnachrichten?
        - Makro-Wirtschaft (Zinsen, Inflation)?
        - Technische Faktoren?
        Halte die Antwort kurz, sachlich und wie ein professioneller Finanzanalyst. Max. 3 Sätze.
        """

        completion = client.chat.completions.create(
            model="qwen/qwen3-235b-a22b-2507:free",  # ✅ Öffentlich verfügbar & stark
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ KI-Analyse fehlgeschlagen: {e}"

# --- HILFSFUNKTIONEN ---

def waehrung_fuer_symbol(symbol):
    """Gibt die Währung basierend auf dem Tickersuffix zurück"""
    if symbol.endswith(".DE") or symbol.endswith(".PA") or symbol.endswith(".MI"):
        return "EUR"
    elif symbol.endswith(".AX"):
        return "AUD"
    elif symbol.endswith(".TO"):
        return "CAD"
    elif symbol.endswith(".L"):
        return "GBP"
    else:
        return "USD"  # Standard: z. B. AAPL, NVDA, META

def lade_aktien_liste(pfad="aktien.json"):
    try:
        with open(pfad, "r") as f:
            data = json.load(f)
            # Sicherstellen, dass alle Werte float sind
            return {k: float(v) for k, v in data.items()}
    except FileNotFoundError:
        print("Keine aktien.json gefunden. Erstelle neue Liste...")
        speichere_aktien_liste({})
        return {}
    except Exception as e:
        print(f"Fehler beim Laden der Aktienliste: {e}")
        return {}

def speichere_aktien_liste(liste, pfad="aktien.json"):
    try:
        with open(pfad, "w") as f:
            json.dump(liste, f, indent=2)
        return True
    except Exception as e:
        print(f"Fehler beim Speichern der Aktienliste: {e}")
        return False
    

def hole_firmenname(symbol):
    """
    Holt den lesbaren Firmennamen von Yahoo Finance.
    Gibt den Ticker zurück, falls kein Name gefunden wird.
    """
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        # Versuche longName, dann shortName, fallback auf Symbol
        name = info.get("longName") or info.get("shortName") or symbol
        return name.strip()
    except:
        return symbol  # Falls Netzwerkfehler oder Timeout
    
    
# --- MONITORING (erweitert: + und - mit richtiger Währung) ---
async def aktien_monitoring(app):
    print("Aktien-Monitoring gestartet (alle 60 Sekunden)")
    while True:
        aktien_liste = lade_aktien_liste()
        if not aktien_liste:
            await asyncio.sleep(60)
            continue

        for symbol, grenze in aktien_liste.items():
            try:
                stock = yf.Ticker(symbol)
                data = stock.history(period="1d", interval="1m")
                if len(data) < 2:
                    continue

                vorher = data["Close"].iloc[-2]
                aktuell = data["Close"].iloc[-1]
                delta = ((aktuell - vorher) / vorher) * 100

                # 🔢 Nimm den absoluten Betrag der Schwelle
                schwelle_abs = abs(grenze)

                # ⏳ Prüfe Datum (nur heute)
                timestamp = data.index[-1]
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.tz_localize(None)
                datum = timestamp.strftime("%Y-%m-%d")
                uhrzeit = timestamp.strftime("%H:%M:%S")
                heute = datetime.now().strftime("%Y-%m-%d")

                if datum != heute:
                    continue  # Nur heuteige Daten verarbeiten

                aktueller_preis = round(aktuell, 2)
                waehrung = waehrung_fuer_symbol(symbol)  # Dynamische Währung
                text = None

                # 🔺 Prüfe: starker Anstieg?
                if delta >= schwelle_abs:
                    firmenname = hole_firmenname(symbol)
                    ki_text = ki_analyse_fuer_aktie(symbol, delta, aktueller_preis, waehrung, firmenname)
                    text = (
                        f"🟢 *{firmenname}* (`{symbol}`) ist um +{delta:.2f}% **gestiegen**!\n"
                        f"💰 Kurs: *{aktueller_preis} {waehrung}*\n"
                        f"📅 {datum}, {uhrzeit}\n"
                        f"🎯 Schwelle: ±{schwelle_abs:.2f}%\n\n"
                        f"🧠 *KI-Analyse*:\n{ki_text}"
                    )

                # 🔻 Prüfe: starker Fall?
                elif delta <= -schwelle_abs:
                    firmenname = hole_firmenname(symbol)
                    ki_text = ki_analyse_fuer_aktie(symbol, delta, aktueller_preis, waehrung, firmenname)
                    text = (
                        f"🔴 *{firmenname}* (`{symbol}`) ist um {delta:.2f}% **gefallen**!\n"
                        f"💰 Kurs: *{aktueller_preis} {waehrung}*\n"
                        f"📅 {datum}, {uhrzeit}\n"
                        f"🛑 Schwelle: ±{schwelle_abs:.2f}%\n\n"
                        f"🧠 *KI-Analyse*:\n{ki_text}"
                    )

                # ✉️ Sende Nachricht, wenn ausgelöst
                if text:
                    await app.bot.send_message(
                        chat_id=DEINE_CHAT_ID,
                        text=text,
                        parse_mode="Markdown"
                    )
                    logging.info(f"Alarm gesendet für {symbol}: {delta:.2f}%")

            except Exception as e:
                logging.error(f"Fehler bei {symbol}: {e}")

        await asyncio.sleep(60)  # Alle 60 Sekunden prüfen

# --- TELEGRAM-COMMANDS ---
async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"💬 Deine Chat-ID ist: `{update.effective_chat.id}`", parse_mode="Markdown")

async def preis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Bitte gib ein Ticker-Symbol an, z. B. `/preis SAP.DE`", parse_mode="Markdown")
        return
    ticker = context.args[0].upper()
    waehrung = waehrung_fuer_symbol(ticker)

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            await update.message.reply_text(f"❌ Symbol `{ticker}` nicht gefunden oder kein Daten verfügbar.", parse_mode="Markdown")
            return
        price = round(data["Close"].iloc[-1], 2)
        await update.message.reply_text(
            f"📊 Kurs von `{ticker}`: **{price} {waehrung}**",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Fehler beim Abrufen von `{ticker}`: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Willkommen beim Aktien-Alarm-Bot!\n"
        "Befehle:\n"
        "• `/preis SYMBOL` – aktueller Kurs\n"
        "• `/setze SYMBOL SCHWELLE` – z. B. `/setze SAP.DE -0,2`\n"
        "• `/setall SCHWELLE` – alle auf ±Schwelle setzen\n"
        "• `/liste` – aktuelle Überwachungsliste\n"
        "• `/chatid` – deine Chat-ID anzeigen"
    )

async def setze_schwelle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Benutzung: `/setze SYMBOL SCHWELLE`\n"
            "Beispiel: `/setze AAPL -0.1` oder `/setze SAP.DE -0,15`",
            parse_mode="Markdown"
        )
        return

    symbol = context.args[0].upper()
    wert_input = context.args[1].replace(",", ".")  # Komma → Punkt

    try:
        schwelle = float(wert_input)
    except ValueError:
        await update.message.reply_text(
            "❌ Ungültiger Wert. Bitte gib eine Zahl ein, z. B. `-0.1` oder `0,2`."
        )
        return

    aktien_liste = lade_aktien_liste()
    aktien_liste[symbol] = schwelle

    if speichere_aktien_liste(aktien_liste):
        await update.message.reply_text(
            f"✅ Schwellenwert für `{symbol}` auf `{schwelle:.4f}` gesetzt.\n"
            f"🔍 Ab jetzt wird ±{abs(schwelle):.2f}% überwacht.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Fehler beim Speichern der Liste.")

async def setze_alle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Benutzung: `/setall SCHWELLE`\n"
            "Beispiel: `/setall -0.5` oder `/setall 0,2`",
            parse_mode="Markdown"
        )
        return

    wert_input = context.args[0].replace(",", ".")  # Komma → Punkt

    try:
        neuer_wert = float(wert_input)
    except ValueError:
        await update.message.reply_text("❌ Bitte eine gültige Zahl eingeben, z. B. `-0.15` oder `0,3`.")
        return

    aktien_liste = lade_aktien_liste()
    for symbol in aktien_liste:
        aktien_liste[symbol] = neuer_wert

    if speichere_aktien_liste(aktien_liste):
        await update.message.reply_text(
            f"✅ Alle Schwellenwerte auf `{neuer_wert:.4f}` gesetzt.\n"
            f"🔍 Ab jetzt wird ±{abs(neuer_wert):.2f}% überwacht.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Fehler beim Speichern.")

async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    aktien_liste = lade_aktien_liste()
    if not aktien_liste:
        await update.message.reply_text("📋 Keine Aktien zur Überwachung.")
        return

    text = "📊 Aktuelle Überwachung (± in beide Richtungen):\n"
    for symbol, grenze in aktien_liste.items():
        schwelle_abs = abs(grenze)
        waehrung = waehrung_fuer_symbol(symbol)
        text += f"• `{symbol}` → ±{schwelle_abs:.2f}% ({waehrung})\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# --- HAUPTFUNKTION ---
async def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Befehle hinzufügen
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("preis", preis))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("setze", setze_schwelle))
    app.add_handler(CommandHandler("setall", setze_alle))
    app.add_handler(CommandHandler("liste", liste))

    # Starte Monitoring im Hintergrund
    asyncio.create_task(aktien_monitoring(app))

    print("✅ Bot läuft... (STRG+C zum Beenden)")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
