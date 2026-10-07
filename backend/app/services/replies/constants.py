"""Phase 9 reply intelligence constants."""

ALLOWED_INTENTS = frozenset(
    {
        "interested",
        "meeting_request",
        "question",
        "pricing_question",
        "needs_information",
        "not_interested",
        "unsubscribe",
        "wrong_contact",
        "out_of_office",
        "automatic_reply",
        "complaint",
        "other",
        "unknown",
    }
)

ALLOWED_SENTIMENTS = frozenset({"positive", "neutral", "negative", "unknown"})
ALLOWED_URGENCIES = frozenset({"high", "medium", "low", "unknown"})

# Conversation statuses
CONV_OPEN = "open"
CONV_INTERESTED = "interested"
CONV_MEETING = "meeting_requested"
CONV_NOT_INTERESTED = "not_interested"
CONV_UNSUBSCRIBE = "unsubscribe"
CONV_CLOSED = "closed"
CONV_NEEDS_HUMAN = "needs_human"

INTENT_TO_CONVERSATION_STATUS = {
    "interested": CONV_INTERESTED,
    "meeting_request": CONV_MEETING,
    "not_interested": CONV_NOT_INTERESTED,
    "unsubscribe": CONV_UNSUBSCRIBE,
    "complaint": CONV_UNSUBSCRIBE,
    "question": CONV_NEEDS_HUMAN,
    "pricing_question": CONV_NEEDS_HUMAN,
    "needs_information": CONV_NEEDS_HUMAN,
    "wrong_contact": CONV_NEEDS_HUMAN,
    "out_of_office": CONV_OPEN,
    "automatic_reply": CONV_OPEN,
    "other": CONV_NEEDS_HUMAN,
    "unknown": CONV_NEEDS_HUMAN,
}

UNSUBSCRIBE_PHRASES = (
    "unsubscribe",
    "remove me",
    "stop emailing",
    "stop contacting",
    "don't contact me",
    "do not contact",
    "take me off",
    "remove from your list",
    "mailing list",
)

MEETING_PHRASES = (
    "schedule a call",
    "book a meeting",
    "are you free",
    "let's talk",
    "lets talk",
    "can we talk",
    "set up a call",
    "meet next",
    "available wednesday",
    "available tuesday",
    "wednesday afternoon",
    "tuesday afternoon",
    "free on",
)

NOT_INTERESTED_PHRASES = (
    "not interested",
    "no thanks",
    "no thank you",
    "please don't",
    "please do not",
)

PRICING_PHRASES = (
    "what does it cost",
    "how much",
    "pricing",
    "price",
    "cost",
    "rates",
    "quote",
)

INTERESTED_PHRASES = (
    "sounds interesting",
    "interested",
    "tell me more",
    "sounds good",
    "I'd be interested",
    "i'd be interested",
    "i am interested",
)

CLASSIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "intent_confidence": {"type": "number"},
        "sentiment": {"type": "string"},
        "sentiment_confidence": {"type": "number"},
        "urgency": {"type": "string"},
        "requires_human": {"type": "boolean"},
        "reason": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "sentiment", "urgency", "requires_human", "reason", "evidence"],
}
