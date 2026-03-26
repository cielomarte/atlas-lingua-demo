from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

from ...models.domain import SessionRecord, TopicHit, TutorTurnPayload, VocabularyItem
from .base import EventCallback, SpeechProvider, TutorProvider

MOCK_TRANSCRIPTS = [
    "I would like to order a coffee, please.",
    "Can you help me ask for directions to the museum?",
    "How do I say that I am learning slowly but really enjoying the language?",
    "I need to buy two train tickets for tomorrow morning.",
    "Can we practice how to greet someone politely?",
]


class MockSpeechProvider(SpeechProvider):
    async def stream_turn(
        self,
        browser_ws: WebSocket,
        session: SessionRecord,
        on_event: EventCallback,
    ) -> str:
        custom_transcript: str | None = None
        saw_audio = False
        await on_event({"type": "status", "status": "listening", "message": "Listening in mock mode…"})

        while True:
            message = await browser_ws.receive()
            message_type = message.get("type")
            if message_type == "websocket.disconnect":
                break
            if message_type != "websocket.receive":
                continue

            if message.get("bytes"):
                saw_audio = True
                continue

            text = message.get("text")
            if not text:
                continue

            control = json.loads(text)
            if control.get("type") == "mock_transcript":
                custom_transcript = (control.get("text") or "").strip()
                continue
            if control.get("type") in {"finalize", "close", "CloseStream"}:
                break

        transcript = custom_transcript or self._pick_transcript(session, saw_audio)
        if transcript:
            await on_event(
                {
                    "type": "transcript_update",
                    "event": "StartOfTurn",
                    "transcript": " ".join(transcript.split()[:4]),
                    "confidence": 0.12,
                }
            )
            await asyncio.sleep(0.02)
            await on_event(
                {
                    "type": "transcript_update",
                    "event": "EndOfTurn",
                    "transcript": transcript,
                    "confidence": 0.88,
                }
            )
        return transcript

    async def transcribe_bytes(self, audio_bytes: bytes, content_type: str | None = None, filename: str | None = None) -> str:
        del content_type, filename
        session = SessionRecord(
            target_language="en",
            voice_model="aura-2-thalia-en",
            speech_lang_tag="en-US",
            difficulty="beginner",
        )
        return self._pick_transcript(session, saw_audio=bool(audio_bytes))

    async def synthesize(self, text: str, voice_model: str) -> tuple[bytes | None, str | None, str | None]:
        return None, None, None

    async def summarize(self, text: str) -> str:
        trimmed = " ".join(text.split())
        if not trimmed:
            return "No conversation available to summarize."
        sentences = [line.strip() for line in text.splitlines() if line.strip()]
        focus = "; ".join(sentences[:4])
        return f"Mock summary: the learner practiced a short conversation. Key moments included {focus}."

    async def detect_topics(self, text: str) -> list[TopicHit]:
        lowered = text.lower()
        topics: list[TopicHit] = []
        rules = [
            ("coffee", "Ordering food or drinks", 0.93),
            ("museum", "Directions and navigation", 0.90),
            ("language", "Learning and self-expression", 0.87),
            ("train", "Travel and transportation", 0.89),
            ("greet", "Greetings and politeness", 0.88),
        ]
        for keyword, label, score in rules:
            if keyword in lowered:
                topics.append(TopicHit(topic=label, confidence_score=score, source_text=keyword))
        if not topics:
            topics.append(TopicHit(topic="General conversation", confidence_score=0.72, source_text="conversation"))
        return topics

    def _pick_transcript(self, session: SessionRecord, saw_audio: bool) -> str:
        if not saw_audio:
            return ""
        return MOCK_TRANSCRIPTS[len(session.turns) % len(MOCK_TRANSCRIPTS)]


class MockTutorProvider(TutorProvider):
    async def generate_turn(self, session: SessionRecord, learner_english: str) -> TutorTurnPayload:
        language = session.target_language
        lowered = learner_english.lower()

        if "coffee" in lowered:
            return self._coffee(language)
        if "museum" in lowered or "direction" in lowered:
            return self._museum(language)
        if "learning slowly" in lowered or "enjoying the language" in lowered:
            return self._learning(language)
        if "train" in lowered or "tickets" in lowered:
            return self._train(language)
        if "greet" in lowered or "politely" in lowered:
            return self._greeting(language)
        return self._generic(language, learner_english)

    def _payload(
        self,
        translated: str,
        tutor: str,
        hint: str,
        note: str,
        vocab: list[VocabularyItem],
        romanized: str = "",
    ) -> TutorTurnPayload:
        return TutorTurnPayload(
            translated_user_utterance=translated,
            translated_user_utterance_romanized=romanized,
            tutor_reply_target=tutor,
            tutor_reply_english_hint=hint,
            teacher_note=note,
            vocabulary=vocab,
        )

    def _coffee(self, language: str) -> TutorTurnPayload:
        data = {
            "es": ("Me gustaría pedir un café, por favor.", "¿Lo quieres con leche o solo?", "Would you like it with milk or black?", "Use 'me gustaría' for a polite request.", [VocabularyItem(word="café", meaning="coffee"), VocabularyItem(word="pedir", meaning="to order")], ""),
            "de": ("Ich möchte bitte einen Kaffee bestellen.", "Möchtest du ihn mit Milch oder schwarz?", "Would you like it with milk or black?", "'Ich möchte' is a natural polite request form.", [VocabularyItem(word="Kaffee", meaning="coffee"), VocabularyItem(word="bestellen", meaning="to order")], ""),
            "fr": ("Je voudrais commander un café, s'il vous plaît.", "Vous le voulez avec du lait ou noir ?", "Would you like it with milk or black?", "'Je voudrais' softens the request politely.", [VocabularyItem(word="café", meaning="coffee"), VocabularyItem(word="commander", meaning="to order")], ""),
            "nl": ("Ik wil graag een koffie bestellen, alstublieft.", "Wilt u hem met melk of zwart?", "Would you like it with milk or black?", "'Ik wil graag' is a friendly polite pattern.", [VocabularyItem(word="koffie", meaning="coffee"), VocabularyItem(word="bestellen", meaning="to order")], ""),
            "it": ("Vorrei ordinare un caffè, per favore.", "Lo vuoi con il latte o amaro?", "Would you like it with milk or black?", "'Vorrei' is useful for polite requests.", [VocabularyItem(word="caffè", meaning="coffee"), VocabularyItem(word="ordinare", meaning="to order")], ""),
            "ja": ("コーヒーをお願いします。", "ミルク入りにしますか、それともブラックにしますか。", "Would you like it with milk or black?", "お願い します is a polite request pattern.", [VocabularyItem(word="コーヒー", meaning="coffee"), VocabularyItem(word="ブラック", meaning="black coffee")], "Kōhī o onegai shimasu."),
            "en": ("I would like to order a coffee, please.", "Would you like it with milk or black?", "Would you like it with milk or black?", "A soft request uses 'would like'.", [VocabularyItem(word="coffee", meaning="coffee"), VocabularyItem(word="order", meaning="request to buy")], ""),
        }
        return self._payload(*data[language])

    def _museum(self, language: str) -> TutorTurnPayload:
        data = {
            "es": ("¿Puede ayudarme a pedir indicaciones para ir al museo?", "Claro. Puedes decir: ¿Dónde está el museo?", "Sure. You can say: Where is the museum?", "Questions often begin with ¿Dónde está...?.", [VocabularyItem(word="museo", meaning="museum"), VocabularyItem(word="indicaciones", meaning="directions")], ""),
            "de": ("Können Sie mir helfen, nach dem Weg zum Museum zu fragen?", "Natürlich. Du kannst sagen: Wo ist das Museum?", "Of course. You can say: Where is the museum?", "'Wo ist ...?' is a simple direction question.", [VocabularyItem(word="Museum", meaning="museum"), VocabularyItem(word="Weg", meaning="way / route")], ""),
            "fr": ("Pouvez-vous m'aider à demander le chemin pour aller au musée ?", "Bien sûr. Vous pouvez dire : Où est le musée ?", "Of course. You can say: Where is the museum?", "Use 'Où est ... ?' for location questions.", [VocabularyItem(word="musée", meaning="museum"), VocabularyItem(word="chemin", meaning="way / directions")], ""),
            "nl": ("Kunt u mij helpen om de weg naar het museum te vragen?", "Natuurlijk. Je kunt zeggen: Waar is het museum?", "Of course. You can say: Where is the museum?", "'Waar is ...?' is the core location question.", [VocabularyItem(word="museum", meaning="museum"), VocabularyItem(word="weg", meaning="way")], ""),
            "it": ("Può aiutarmi a chiedere indicazioni per il museo?", "Certo. Puoi dire: Dov'è il museo?", "Sure. You can say: Where is the museum?", "Dov'è is a common contraction for asking location.", [VocabularyItem(word="museo", meaning="museum"), VocabularyItem(word="indicazioni", meaning="directions")], ""),
            "ja": ("博物館への行き方を聞くのを手伝ってもらえますか。", "もちろんです。『博物館はどこですか。』と言えます。", "Of course. You can say: Where is the museum?", "どこですか is a core location pattern.", [VocabularyItem(word="博物館", meaning="museum"), VocabularyItem(word="行き方", meaning="how to get there")], "Hakubutsukan e no ikikata o kiku no o tetsudatte moraemasu ka."),
            "en": ("Can you help me ask for directions to the museum?", "Of course. You can say: Where is the museum?", "Of course. You can say: Where is the museum?", "Clear location questions are short and direct.", [VocabularyItem(word="museum", meaning="museum"), VocabularyItem(word="directions", meaning="route guidance")], ""),
        }
        return self._payload(*data[language])

    def _learning(self, language: str) -> TutorTurnPayload:
        data = {
            "es": ("Estoy aprendiendo despacio, pero de verdad disfruto el idioma.", "Eso suena muy bien. ¿Qué parte disfrutas más?", "That sounds great. What part do you enjoy most?", "Present tense works well for ongoing learning habits.", [VocabularyItem(word="aprendiendo", meaning="learning"), VocabularyItem(word="disfruto", meaning="I enjoy")], ""),
            "de": ("Ich lerne langsam, aber ich genieße die Sprache wirklich.", "Das klingt gut. Welchen Teil magst du am meisten?", "That sounds good. Which part do you like most?", "German often keeps the verb early in the sentence.", [VocabularyItem(word="lernen", meaning="to learn"), VocabularyItem(word="genießen", meaning="to enjoy")], ""),
            "fr": ("J'apprends lentement, mais j'aime vraiment la langue.", "C'est très bien. Quelle partie préférez-vous ?", "That's very good. Which part do you prefer?", "French often uses 'j'aime' for simple preference.", [VocabularyItem(word="apprendre", meaning="to learn"), VocabularyItem(word="langue", meaning="language")], ""),
            "nl": ("Ik leer langzaam, maar ik geniet echt van de taal.", "Dat klinkt goed. Welk deel vind je het leukst?", "That sounds good. Which part do you enjoy most?", "'Ik geniet van' is a useful enjoyment pattern.", [VocabularyItem(word="leren", meaning="to learn"), VocabularyItem(word="taal", meaning="language")], ""),
            "it": ("Sto imparando lentamente, ma mi piace davvero la lingua.", "Molto bene. Quale parte ti piace di più?", "Very good. Which part do you like most?", "Sto + gerund can show an ongoing action.", [VocabularyItem(word="imparando", meaning="learning"), VocabularyItem(word="lingua", meaning="language")], ""),
            "ja": ("ゆっくり学んでいますが、この言語を本当に楽しんでいます。", "それはいいですね。何がいちばん楽しいですか。", "That is nice. What do you enjoy most?", "〜ています can describe an ongoing state or activity.", [VocabularyItem(word="学んでいます", meaning="am learning"), VocabularyItem(word="楽しい", meaning="fun / enjoyable")], "Yukkuri manande imasu ga, kono gengo o hontō ni tanoshinde imasu."),
            "en": ("I am learning slowly, but I really enjoy the language.", "That sounds great. What part do you enjoy most?", "That sounds great. What part do you enjoy most?", "The present tense communicates an ongoing journey.", [VocabularyItem(word="enjoy", meaning="like very much"), VocabularyItem(word="language", meaning="system of communication")], ""),
        }
        return self._payload(*data[language])

    def _train(self, language: str) -> TutorTurnPayload:
        data = {
            "es": ("Necesito comprar dos billetes de tren para mañana por la mañana.", "Claro. Puedes preguntar: ¿Cuánto cuestan dos billetes?", "Sure. You can ask: How much do two tickets cost?", "Use numbers directly before the noun.", [VocabularyItem(word="billetes", meaning="tickets"), VocabularyItem(word="mañana", meaning="tomorrow / morning depending on context")], ""),
            "de": ("Ich muss zwei Zugtickets für morgen früh kaufen.", "Klar. Du kannst fragen: Wie viel kosten zwei Tickets?", "Sure. You can ask: How much do two tickets cost?", "Time expressions often sit near the middle of the sentence.", [VocabularyItem(word="Zugticket", meaning="train ticket"), VocabularyItem(word="morgen früh", meaning="tomorrow morning")], ""),
            "fr": ("J'ai besoin d'acheter deux billets de train pour demain matin.", "Bien sûr. Vous pouvez demander : Combien coûtent deux billets ?", "Sure. You can ask: How much do two tickets cost?", "'J'ai besoin de' expresses need naturally.", [VocabularyItem(word="billets", meaning="tickets"), VocabularyItem(word="demain matin", meaning="tomorrow morning")], ""),
            "nl": ("Ik moet twee treinkaartjes kopen voor morgenochtend.", "Zeker. Je kunt vragen: Hoeveel kosten twee kaartjes?", "Sure. You can ask: How much do two tickets cost?", "Compound nouns are common in Dutch.", [VocabularyItem(word="treinkaartjes", meaning="train tickets"), VocabularyItem(word="morgenochtend", meaning="tomorrow morning")], ""),
            "it": ("Devo comprare due biglietti del treno per domani mattina.", "Certo. Puoi chiedere: Quanto costano due biglietti?", "Sure. You can ask: How much do two tickets cost?", "Devo + infinitive is a simple need structure.", [VocabularyItem(word="biglietti", meaning="tickets"), VocabularyItem(word="domani mattina", meaning="tomorrow morning")], ""),
            "ja": ("明日の朝の電車の切符を二枚買う必要があります。", "もちろんです。『切符は二枚でいくらですか。』と聞けます。", "Of course. You can ask: How much are two tickets?", "Counter words matter in Japanese; 枚 is used for flat items like tickets.", [VocabularyItem(word="切符", meaning="ticket"), VocabularyItem(word="二枚", meaning="two flat items")], "Ashita no asa no densha no kippu o nimai kau hitsuyō ga arimasu."),
            "en": ("I need to buy two train tickets for tomorrow morning.", "Sure. You can ask: How much do two tickets cost?", "Sure. You can ask: How much do two tickets cost?", "Be explicit with number plus noun.", [VocabularyItem(word="tickets", meaning="travel passes"), VocabularyItem(word="tomorrow morning", meaning="the next morning")], ""),
        }
        return self._payload(*data[language])

    def _greeting(self, language: str) -> TutorTurnPayload:
        data = {
            "es": ("¿Podemos practicar cómo saludar a alguien con cortesía?", "Claro. Puedes decir: Mucho gusto, ¿cómo está usted?", "Sure. You can say: Nice to meet you, how are you?", "Use usted for a polite register.", [VocabularyItem(word="saludar", meaning="to greet"), VocabularyItem(word="cortesía", meaning="politeness")], ""),
            "de": ("Können wir üben, wie man jemanden höflich begrüßt?", "Gern. Du kannst sagen: Guten Tag, wie geht es Ihnen?", "Gladly. You can say: Good day, how are you?", "Ihnen marks a polite form of address.", [VocabularyItem(word="begrüßen", meaning="to greet"), VocabularyItem(word="höflich", meaning="polite")], ""),
            "fr": ("Pouvons-nous pratiquer comment saluer quelqu'un poliment ?", "Bien sûr. Vous pouvez dire : Bonjour, comment allez-vous ?", "Of course. You can say: Hello, how are you?", "French politeness often uses vous.", [VocabularyItem(word="saluer", meaning="to greet"), VocabularyItem(word="poliment", meaning="politely")], ""),
            "nl": ("Kunnen we oefenen hoe je iemand beleefd begroet?", "Natuurlijk. Je kunt zeggen: Goedendag, hoe gaat het met u?", "Of course. You can say: Good day, how are you?", "Met u keeps the greeting polite.", [VocabularyItem(word="begroeten", meaning="to greet"), VocabularyItem(word="beleefd", meaning="polite")], ""),
            "it": ("Possiamo fare pratica su come salutare qualcuno con gentilezza?", "Certo. Puoi dire: Buongiorno, come sta?", "Sure. You can say: Good morning / hello, how are you?", "Sta is polite when addressing someone formally.", [VocabularyItem(word="salutare", meaning="to greet"), VocabularyItem(word="gentilezza", meaning="kindness / politeness")], ""),
            "ja": ("丁寧にあいさつする言い方を練習できますか。", "もちろんです。『こんにちは、お元気ですか。』と言えます。", "Of course. You can say: Hello, how are you?", "丁寧な Japanese often uses polite verb endings like です / ます.", [VocabularyItem(word="丁寧", meaning="polite"), VocabularyItem(word="あいさつ", meaning="greeting")], "Teinei ni aisatsu suru iikata o renshū dekimasu ka."),
            "en": ("Can we practice how to greet someone politely?", "Of course. You can say: Hello, how are you?", "Of course. You can say: Hello, how are you?", "Polite greetings are short and warm.", [VocabularyItem(word="greet", meaning="say hello"), VocabularyItem(word="politely", meaning="with courtesy")], ""),
        }
        return self._payload(*data[language])

    def _generic(self, language: str, learner_english: str) -> TutorTurnPayload:
        labels = {
            "es": (f"[Demostración] {learner_english}", "¿Puedes repetirlo un poco más despacio?", "Can you repeat that a little more slowly?"),
            "de": (f"[Demo] {learner_english}", "Kannst du das etwas langsamer wiederholen?", "Can you repeat that a little more slowly?"),
            "fr": (f"[Démo] {learner_english}", "Pouvez-vous le répéter un peu plus lentement ?", "Can you repeat that a little more slowly?"),
            "nl": (f"[Demo] {learner_english}", "Kun je dat iets langzamer herhalen?", "Can you repeat that a little more slowly?"),
            "it": (f"[Demo] {learner_english}", "Puoi ripeterlo un po' più lentamente?", "Can you repeat that a little more slowly?"),
            "ja": (f"【デモ】{learner_english}", "もう少しゆっくり言ってもらえますか。", "Could you say that a little more slowly?"),
            "en": (learner_english, "Could you say that a little more slowly?", "Could you say that a little more slowly?"),
        }
        translated, tutor, hint = labels[language]
        return TutorTurnPayload(
            translated_user_utterance=translated,
            translated_user_utterance_romanized="" if language != "ja" else learner_english,
            tutor_reply_target=tutor,
            tutor_reply_english_hint=hint,
            teacher_note="Mock mode is using canned tutoring content.",
            vocabulary=[VocabularyItem(word="demo", meaning="demonstration")],
        )
