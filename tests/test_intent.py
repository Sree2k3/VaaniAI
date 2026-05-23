from app.intent import detect_intent


def test_detects_hinglish_booking_with_specialization() -> None:
    result = detect_intent("Mujhe skin doctor ka appointment chahiye")

    assert result.intent == "book_appointment"
    assert result.specialization == "dermatologist"


def test_detects_slot_selection() -> None:
    result = detect_intent("Kal 10 baje")

    assert result.intent == "slot_selected"


def test_detects_name() -> None:
    result = detect_intent("Mera naam Rahul hai")

    assert result.intent == "name_provided"
    assert result.name == "Rahul"


def test_detects_confirmation() -> None:
    result = detect_intent("Yes confirm")

    assert result.intent == "affirmative"


def test_detects_inquiry() -> None:
    result = detect_intent("What are your clinic timings and fees?")

    assert result.intent == "doctor_inquiry"


def test_detects_gender_age_and_phone() -> None:
    gender = detect_intent("female")
    age = detect_intent("I am 27 years old")
    phone = detect_intent("my number is 9876543210")

    assert gender.intent == "gender_provided"
    assert gender.gender == "female"
    assert age.intent == "age_provided"
    assert age.age == 27
    assert phone.intent == "phone_provided"
    assert phone.phone == "9876543210"


def test_maps_symptom_to_specialization() -> None:
    result = detect_intent("I have chest pain, can you book an appointment?")

    assert result.intent == "book_appointment"
    assert result.specialization == "cardiologist"


def test_accepts_direct_specialist_request() -> None:
    result = detect_intent("I want to consult a neurologist")

    assert result.intent == "book_appointment"
    assert result.specialization == "neurologist"


def test_maps_new_symptoms_to_specialists() -> None:
    assert detect_intent("I have knee pain").specialization == "orthopedic"
    assert detect_intent("I have blurred vision").specialization == "ophthalmologist"
    assert detect_intent("I have breathing problem").specialization == "pulmonologist"


def test_detects_spoken_age_words() -> None:
    result = detect_intent("Twenty-three years")

    assert result.intent == "age_provided"
    assert result.age == 23


def test_detects_spoken_phone_digits() -> None:
    result = detect_intent("eight two nine three zero one four seven eight seven")

    assert result.intent == "phone_provided"
    assert result.phone == "8293014787"


def test_detects_spelled_and_hindi_gender() -> None:
    spelled = detect_intent("M A L E")
    hindi = detect_intent("मेल")

    assert spelled.intent == "gender_provided"
    assert spelled.gender == "male"
    assert hindi.intent == "gender_provided"
    assert hindi.gender == "male"


def test_detects_hindi_symptoms_name_age_and_phone() -> None:
    symptom = detect_intent("मेरे सीने में दर्द है")
    name = detect_intent("मेरा नाम श्रीकांत पटनायक है")
    age = detect_intent("तेईस साल")
    phone = detect_intent("आठ दो नौ तीन शून्य एक चार सात आठ सात")

    assert symptom.intent == "specialization_selected"
    assert symptom.specialization == "cardiologist"
    assert name.intent == "name_provided"
    assert name.name == "श्रीकांत पटनायक"
    assert age.intent == "age_provided"
    assert age.age == 23
    assert phone.intent == "phone_provided"
    assert phone.phone == "8293014787"
