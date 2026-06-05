import re
from dataclasses import dataclass


SPECIALIZATION_ALIASES = {
    "dermatologist": ["dermatologist", "skin", "skin doctor", "twacha", "chamdi", "त्वचा", "चमड़ी", "स्किन"],
    "general physician": [
        "general physician",
        "physician",
        "doctor",
        "fever",
        "cold",
        "bukhar",
        "viral",
        "pet",
        "stomach",
        "पेट",
        "बुखार",
        "सर्दी",
        "डॉक्टर",
    ],
    "dentist": ["dentist", "dental", "tooth", "teeth", "daant", "दांत", "दाँत", "डेंटिस्ट"],
    "cardiologist": ["cardiologist", "heart", "dil", "chest", "seena", "सीना", "छाती", "दिल", "हार्ट"],
    "pediatrician": ["pediatrician", "child", "children", "bachcha", "kids", "बच्चा", "बच्चे"],
}

SYMPTOM_TO_SPECIALIZATION = {
    "stomach": "general physician",
    "stomach pain": "general physician",
    "abdomen": "general physician",
    "gastric": "general physician",
    "pet dard": "general physician",
    "पेट दर्द": "general physician",
    "chest pain": "cardiologist",
    "chest problem": "cardiologist",
    "heart pain": "cardiologist",
    "palpitation": "cardiologist",
    "seene mein dard": "cardiologist",
    "seena dard": "cardiologist",
    "छाती में दर्द": "cardiologist",
    "सीने में दर्द": "cardiologist",
    "दिल में दर्द": "cardiologist",
}

SPECIALIZATION_ALIASES.update(
    {
        "orthopedic": ["orthopedic", "orthopaedic", "bone doctor", "joint doctor", "bone", "joint", "knee", "back pain", "fracture"],
        "neurologist": ["neurologist", "neuro", "brain doctor", "nerve doctor", "migraine", "seizure", "fits", "numbness"],
        "ent specialist": ["ent", "ent specialist", "ear doctor", "nose doctor", "throat doctor", "ear", "nose", "throat", "sinus"],
        "gynecologist": ["gynecologist", "gynaecologist", "gynec", "gynac", "lady doctor", "women doctor", "pregnancy", "period"],
        "ophthalmologist": ["ophthalmologist", "eye doctor", "eye specialist", "eye", "vision", "aankh"],
        "psychiatrist": ["psychiatrist", "mental health", "anxiety", "depression", "panic", "stress"],
        "endocrinologist": ["endocrinologist", "diabetes doctor", "thyroid doctor", "diabetes", "thyroid", "hormone", "sugar"],
        "pulmonologist": ["pulmonologist", "lung doctor", "chest doctor", "breathing", "asthma", "wheezing", "lungs"],
    }
)

SYMPTOM_TO_SPECIALIZATION.update(
    {
        "bone pain": "orthopedic",
        "joint pain": "orthopedic",
        "knee pain": "orthopedic",
        "back pain": "orthopedic",
        "fracture": "orthopedic",
        "migraine": "neurologist",
        "seizure": "neurologist",
        "fits": "neurologist",
        "numbness": "neurologist",
        "ear pain": "ent specialist",
        "throat pain": "ent specialist",
        "sinus": "ent specialist",
        "nose blockage": "ent specialist",
        "period pain": "gynecologist",
        "irregular periods": "gynecologist",
        "pregnancy": "gynecologist",
        "eye pain": "ophthalmologist",
        "blurred vision": "ophthalmologist",
        "red eyes": "ophthalmologist",
        "anxiety": "psychiatrist",
        "depression": "psychiatrist",
        "panic attack": "psychiatrist",
        "diabetes": "endocrinologist",
        "thyroid": "endocrinologist",
        "breathing problem": "pulmonologist",
        "asthma": "pulmonologist",
        "wheezing": "pulmonologist",
    }
)

BOOKING_WORDS = [
    "book",
    "appointment",
    "schedule",
    "milna",
    "chahiye",
    "dikhana",
    "consult",
    "दिखाना",
    "मिलना",
    "अपॉइंटमेंट",
    "बुक",
]
INQUIRY_WORDS = [
    "fee",
    "fees",
    "address",
    "location",
    "timing",
    "time",
    "open",
    "close",
    "contact",
    "price",
    "फीस",
    "पता",
    "टाइम",
]
AFFIRMATIVE_WORDS = ["yes", "sure", "confirm", "okay", "ok", "haan", "ha", "ji", "हाँ", "हा", "जी", "कन्फर्म"]
NEGATIVE_WORDS = ["no", "cancel", "not now", "nahi", "nahin", "नहीं", "नही", "कैंसल"]
LANGUAGE_SWITCH_WORDS = ["hindi mein", "speak hindi", "english mein", "speak english", "hinglish", "हिंदी में", "इंग्लिश में"]
REPEAT_LAST_WORDS = ["same doctor", "last doctor", "again", "pichle doctor", "पिछले डॉक्टर"]
GENDER_WORDS = {"male": "male", "female": "female", "other": "other", "m": "male", "f": "female"}
GENDER_ALIASES = {
    "male": ["male", "mail", "m a l e", "man", "boy", "ladka", "पुरुष", "मेल", "आदमी", "लड़का"],
    "female": ["female", "femail", "f e m a l e", "woman", "girl", "ladki", "महिला", "फीमेल", "औरत", "लड़की"],
    "other": ["other", "non binary", "non-binary"],
}
NUMBER_WORDS = {
    "zero": 0,
    "oh": 0,
    "o": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fourty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
HINDI_NUMBER_WORDS = {
    "दस": 10,
    "ग्यारह": 11,
    "बारह": 12,
    "तेरह": 13,
    "चौदह": 14,
    "पंद्रह": 15,
    "सोलह": 16,
    "सत्रह": 17,
    "अठारह": 18,
    "उन्नीस": 19,
    "बीस": 20,
    "इक्कीस": 21,
    "बाईस": 22,
    "तेईस": 23,
    "चौबीस": 24,
    "पच्चीस": 25,
    "छब्बीस": 26,
    "सत्ताईस": 27,
    "अट्ठाईस": 28,
    "उनतीस": 29,
    "तीस": 30,
    "चालीस": 40,
    "पचास": 50,
    "साठ": 60,
    "सत्तर": 70,
    "अस्सी": 80,
    "नब्बे": 90,
}
DIGIT_WORDS = {word: str(value) for word, value in NUMBER_WORDS.items() if 0 <= value <= 9}
DIGIT_WORDS.update(
    {
        "०": "0",
        "१": "1",
        "२": "2",
        "३": "3",
        "४": "4",
        "५": "5",
        "६": "6",
        "७": "7",
        "८": "8",
        "९": "9",
        "शून्य": "0",
        "जीरो": "0",
        "एक": "1",
        "दो": "2",
        "तीन": "3",
        "चार": "4",
        "पांच": "5",
        "पाँच": "5",
        "छह": "6",
        "सात": "7",
        "आठ": "8",
        "नौ": "9",
    }
)


@dataclass(frozen=True)
class IntentResult:
    intent: str
    specialization: str | None = None
    slot_hint: str | None = None
    name: str | None = None
    gender: str | None = None
    age: int | None = None
    phone: str | None = None


def detect_intent(message: str) -> IntentResult:
    text = message.strip()
    lowered = text.lower()

    if any(word in lowered for word in LANGUAGE_SWITCH_WORDS):
        return IntentResult("language_switch")
    if any(word in lowered for word in REPEAT_LAST_WORDS):
        return IntentResult("repeat_last_doctor")

    if any(word in lowered for word in INQUIRY_WORDS):
        return IntentResult("doctor_inquiry")

    specialization = extract_specialization(lowered)
    if specialization:
        if any(word in lowered for word in BOOKING_WORDS):
            return IntentResult("book_appointment", specialization=specialization)
        return IntentResult("specialization_selected", specialization=specialization)

    if any(marker in lowered for marker in ["name is", "naam", "नाम"]):
        return IntentResult("name_provided", name=extract_name(text))

    gender = extract_gender(lowered)
    if gender:
        return IntentResult("gender_provided", gender=gender)

    phone = extract_phone(lowered)
    if phone:
        return IntentResult("phone_provided", phone=phone)

    if any(keyword in lowered for keyword in ["age", "years", "year", "saal", "umra", "umar", "à¤¸à¤¾à¤²", "à¤‰à¤®à¥à¤°"]):
        age = extract_age(lowered)
        if age is not None:
            return IntentResult("age_provided", age=age)

    if looks_like_slot(lowered):
        return IntentResult("slot_selected", slot_hint=lowered)

    age = extract_age(lowered)
    if age is not None:
        return IntentResult("age_provided", age=age)

    tokens = set(tokenize_words(lowered))
    if any(word in tokens for word in AFFIRMATIVE_WORDS):
        return IntentResult("affirmative")
    if any(word in tokens for word in NEGATIVE_WORDS):
        return IntentResult("negative")

    if any(word in lowered for word in BOOKING_WORDS):
        return IntentResult("book_appointment")

    return IntentResult("unknown")


def extract_specialization(lowered: str) -> str | None:
    for symptom, specialization in SYMPTOM_TO_SPECIALIZATION.items():
        if phrase_matches(lowered, symptom):
            return specialization
    for specialization, aliases in SPECIALIZATION_ALIASES.items():
        if any(phrase_matches(lowered, alias) for alias in aliases):
            return specialization
    return None


def phrase_matches(text: str, phrase: str) -> bool:
    phrase = phrase.lower().strip()
    if not phrase:
        return False
    if len(phrase) <= 3 or re.fullmatch(r"[a-zA-Z]+", phrase):
        return re.search(rf"(^|[^a-zA-Z]){re.escape(phrase)}([^a-zA-Z]|$)", text) is not None
    return phrase in text


def looks_like_slot(lowered: str) -> bool:
    slot_words = {
        "baje",
        "morning",
        "evening",
        "tomorrow",
        "kal",
        "today",
        "aaj",
        "option",
        "slot",
        "first",
        "second",
        "third",
        "fourth",
        "saturday",
        "sunday",
        "monday",
        "tuesday",
        "june",
        "jun",
        "date",
        "tarikh",
        "tareekh",
    }
    tokens = set(tokenize_words(lowered))
    if any(word in tokens for word in slot_words):
        return True
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(am|pm)\b", lowered):
        return True
    if re.search(r"\b(slot|option|june|jun|date|tarikh|tareekh)\s*\d{1,2}\b", lowered):
        return True
    if re.search(r"\b\d{1,2}(st|nd|rd|th)?\s*(june|jun)\b", lowered):
        return True
    time_words = ["am", "pm", "baje", "morning", "evening", "tomorrow", "kal", "today", "aaj", "बजे", "कल", "आज"]
    tokens = set(tokenize_words(lowered))
    return any(word in tokens for word in time_words)


def extract_name(text: str) -> str:
    normalized = text.replace(".", " ").strip()
    lowered = normalized.lower()
    for marker in ["my name is", "name is", "mera naam", "मेरा नाम", "नाम"]:
        if marker in lowered:
            index = lowered.index(marker) + len(marker)
            candidate = normalized[index:]
            for filler in ["hai", "है", "is"]:
                candidate = candidate.replace(filler, " ")
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if candidate:
                return candidate.title()
    return normalized.title()


def extract_gender(lowered: str) -> str | None:
    compact = re.sub(r"\s+", " ", lowered).strip()
    for value, aliases in GENDER_ALIASES.items():
        if any(re.search(rf"(^|\b){re.escape(alias)}($|\b)", compact) for alias in aliases):
            return value
    for token, value in GENDER_WORDS.items():
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return value
    if "ladka" in lowered or "लड़का" in lowered:
        return "male"
    if "ladki" in lowered or "लड़की" in lowered:
        return "female"
    return None


def extract_age(lowered: str) -> int | None:
    tokens = tokenize_words(lowered)
    if any(keyword in tokens for keyword in ["baje", "morning", "evening", "tomorrow", "kal", "today", "aaj", "बजे", "कल", "आज"]):
        return None
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(am|pm)\b", lowered):
        return None
    spoken_number = parse_spoken_number(lowered)
    if any(keyword in lowered for keyword in ["age", "years", "year", "saal", "umra", "umar", "साल", "उम्र"]):
        match = re.search(r"\b(\d{1,2})\b", lowered)
        if match:
            value = int(match.group(1))
            if 0 < value < 120:
                return value
        if spoken_number is not None and 0 < spoken_number < 120:
            return spoken_number
    if re.fullmatch(r"\s*\d{1,2}\s*", lowered):
        value = int(lowered.strip())
        if 0 < value < 120:
            return value
    if spoken_number is not None and 0 < spoken_number < 120 and len(tokens) <= 3:
        return spoken_number
    return None


def extract_phone(lowered: str) -> str | None:
    digits = normalize_spoken_digits(lowered)
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        return digits
    return None


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+|[\u0900-\u097F]+|\d+", text.replace("-", " ").lower())


def parse_spoken_number(text: str) -> int | None:
    tokens = tokenize_words(text)
    values: list[int] = []
    for token in tokens:
        if token.isdigit():
            values.append(int(token))
        elif token in NUMBER_WORDS:
            values.append(NUMBER_WORDS[token])
        elif token in HINDI_NUMBER_WORDS:
            values.append(HINDI_NUMBER_WORDS[token])
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    if len(values) == 2 and values[0] >= 20 and values[0] % 10 == 0 and 0 < values[1] < 10:
        return values[0] + values[1]
    return None


def normalize_spoken_digits(text: str) -> str:
    output: list[str] = []
    for token in tokenize_words(text):
        if token.isdigit():
            output.append(token)
        elif token in DIGIT_WORDS:
            output.append(DIGIT_WORDS[token])
    return "".join(output)
