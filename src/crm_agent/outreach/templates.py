"""Deterministic, multilingual message templates (offline fallback for the LLM composer).

Templates are *composed* from building blocks chosen by the customer's data – greeting style by
segment, offer line by product/offer, and a "need hook" picked from the strongest behavioural
signal – so two customers rarely get the same message even without an LLM.
"""

from __future__ import annotations


def format_inr(amount: float) -> str:
    """Indian digit grouping: 850000 -> 8,50,000."""
    n = int(round(amount))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + s


SUPPORTED_LANGUAGES = ("English", "Hindi", "Marathi")

HOOKS = {
    "English": {
        "wedding": "Whether it's celebrations coming up or family plans, it helps you manage big expenses without touching your savings.",
        "travel": "If a big trip is on the cards, it can make the journey a lot easier.",
        "education": "Planning ahead for education? This can help you stay a step ahead.",
        "medical": "For unexpected expenses, it gives you quick funds while your savings stay intact.",
        "home_improvement": "Upgrading your home? Spread the cost into easy EMIs.",
        "electronics": "Eyeing a big upgrade? Spread the cost into easy EMIs.",
        "balance_dip": "It's a simple way to keep your savings cushion intact for whatever comes next.",
        "digital": "If you were exploring loan options in our app, this offer is already set up for you.",
        "dining": "Enjoy accelerated rewards every time you dine out.",
        "travel_card": "Enjoy airport lounge access and travel rewards on every trip.",
        "shopping": "Earn accelerated rewards on your online shopping.",
        "rent": "Your monthly rent could become an EMI towards a home of your own.",
        "idle": "It's an easy way to make your idle savings work harder.",
        "default": "It's ready whenever you need it — no branch visit needed.",
    },
    "Hindi": {
        "wedding": "शादी-ब्याह या पारिवारिक समारोह की तैयारी हो, आप अपनी बचत को छुए बिना बड़े खर्च आसानी से संभाल सकते हैं।",
        "travel": "अगर आप कोई बड़ी यात्रा प्लान कर रहे हैं, तो यह आपके सफ़र को आसान बना सकता है।",
        "education": "पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।",
        "medical": "अचानक आए खर्चों के लिए तुरंत फंड पाएं और अपनी बचत सुरक्षित रखें।",
        "home_improvement": "घर को नया रूप देने की सोच रहे हैं? खर्च को आसान EMI में बांटें।",
        "electronics": "कोई बड़ा अपग्रेड प्लान कर रहे हैं? खर्च को आसान EMI में बांटें।",
        "balance_dip": "आगे आने वाली ज़रूरतों के लिए अपनी बचत को सुरक्षित रखने का यह एक आसान तरीका है।",
        "digital": "अगर आप हमारे ऐप में लोन के विकल्प देख रहे थे, तो यह ऑफ़र आपके लिए पहले से तैयार है।",
        "dining": "हर बार बाहर खाने पर ज़्यादा रिवॉर्ड्स पाएं।",
        "travel_card": "हर यात्रा पर एयरपोर्ट लाउंज एक्सेस और ट्रैवल रिवॉर्ड्स का आनंद लें।",
        "shopping": "ऑनलाइन शॉपिंग पर ज़्यादा रिवॉर्ड्स कमाएं।",
        "rent": "आपका मासिक किराया आपके अपने घर की EMI बन सकता है।",
        "idle": "अपनी बचत से ज़्यादा कमाई करने का यह एक आसान तरीका है।",
        "default": "जब भी ज़रूरत हो, यह आपके लिए तैयार है — ब्रांच जाने की ज़रूरत नहीं।",
    },
    "Marathi": {
        "wedding": "लग्नसमारंभ किंवा कौटुंबिक कार्यक्रमाची तयारी असो, बचतीला हात न लावता मोठे खर्च सहज सांभाळा.",
        "travel": "मोठ्या प्रवासाचे नियोजन करत असाल, तर हे तुमचा प्रवास सोपा करू शकते.",
        "education": "शिक्षणाच्या खर्चाचे नियोजन करत आहात? हे उपयोगी पडू शकते.",
        "medical": "अचानक आलेल्या खर्चांसाठी त्वरित निधी मिळवा आणि बचत सुरक्षित ठेवा.",
        "home_improvement": "घराचे नूतनीकरण करायचा विचार आहे? खर्च सोप्या EMI मध्ये विभागा.",
        "electronics": "मोठे अपग्रेड करायचे आहे? खर्च सोप्या EMI मध्ये विभागा.",
        "balance_dip": "पुढील गरजांसाठी तुमची बचत सुरक्षित ठेवण्याचा हा सोपा मार्ग आहे.",
        "digital": "तुम्ही आमच्या ॲपमध्ये लोनचे पर्याय पाहत असाल, तर ही ऑफर तुमच्यासाठी आधीच तयार आहे.",
        "dining": "प्रत्येक वेळी बाहेर जेवताना जास्त रिवॉर्ड्स मिळवा.",
        "travel_card": "प्रत्येक प्रवासात एअरपोर्ट लाउंज आणि ट्रॅव्हल रिवॉर्ड्सचा आनंद घ्या.",
        "shopping": "ऑनलाइन शॉपिंगवर जास्त रिवॉर्ड्स मिळवा.",
        "rent": "तुमचे मासिक भाडे तुमच्या स्वतःच्या घराचा EMI होऊ शकते.",
        "idle": "तुमच्या बचतीवर जास्त परतावा मिळवण्याचा हा सोपा मार्ग आहे.",
        "default": "गरज असेल तेव्हा हे तयार आहे — शाखेत जाण्याची गरज नाही.",
    },
}

TEXT = {
    "English": {
        "greet_casual": "Hi {first_name} 👋",
        "greet_formal": "Dear {salutation} {last_name},",
        "greet_email": "Dear {first_name},",
        "thanks": "Thank you for banking with {bank} for {years} years!",
        "thanks_new": "Thank you for choosing {bank}!",
        "loan": "As one of our {tier} customers, you have a {headline} of up to ₹{amount} at an indicative {rate}% p.a. (EMI from about ₹{emi}/month over {tenure} months).",
        "card": "As one of our {tier} customers, you're eligible for our {headline} with a credit limit of up to ₹{amount}.",
        "deposit": "As one of our {tier} customers, you can lock in our {headline} at {rate}% p.a.{senior}.",
        "investment": "As one of our {tier} customers, you can start a {headline} from just ₹{amount}/month.",
        "senior": " (includes a +{bonus}% senior-citizen bonus)",
        "cta": "Reply YES and I'll set it up for you.",
        "cta_loan": "Reply YES and I'll set it up — funds can reach your account the same day.",
        "cta_email": "Simply reply to this email or call me on {rm_phone} and I'll take care of the rest.",
        "sign": "– {rm_name}, your Relationship Manager, {bank}",
        "sign_email": "Warm regards,\n{rm_name}\nRelationship Manager, {bank}\n{rm_phone}",
        "subject_loan": "{first_name}, your {headline} is ready",
        "subject_other": "{first_name}, an exclusive offer for you from {bank}",
    },
    "Hindi": {
        "greet_casual": "नमस्ते {first_name} जी 🙏",
        "greet_formal": "आदरणीय {first_name} जी,",
        "greet_email": "प्रिय {first_name} जी,",
        "thanks": "{years} साल से {bank} के साथ बने रहने के लिए धन्यवाद!",
        "thanks_new": "{bank} चुनने के लिए धन्यवाद!",
        "loan": "हमारे {tier} ग्राहक होने के नाते, आपके लिए ₹{amount} तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर {rate}% प्रति वर्ष ({tenure} महीनों के लिए EMI लगभग ₹{emi}/माह)।",
        "card": "हमारे {tier} ग्राहक होने के नाते, आप ₹{amount} तक की लिमिट वाले {headline} के लिए पात्र हैं।",
        "deposit": "हमारे {tier} ग्राहक होने के नाते, आप हमारा {headline} {rate}% प्रति वर्ष{senior} पर बुक कर सकते हैं।",
        "investment": "हमारे {tier} ग्राहक होने के नाते, आप सिर्फ़ ₹{amount}/माह से {headline} शुरू कर सकते हैं।",
        "senior": " (वरिष्ठ नागरिक बोनस +{bonus}% सहित)",
        "cta": "डिटेल्स के लिए YES लिखकर भेजें।",
        "cta_loan": "डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।",
        "cta_email": "बस इस ईमेल का जवाब दें या {rm_phone} पर कॉल करें, बाकी सब हम संभाल लेंगे।",
        "sign": "– {rm_name}, रिलेशनशिप मैनेजर, {bank}",
        "sign_email": "सादर,\n{rm_name}\nरिलेशनशिप मैनेजर, {bank}\n{rm_phone}",
        "subject_loan": "{first_name} जी, आपका प्री-अप्रूव्ड ऑफ़र तैयार है",
        "subject_other": "{first_name} जी, {bank} की ओर से आपके लिए खास ऑफ़र",
    },
    "Marathi": {
        "greet_casual": "नमस्कार {first_name} 🙏",
        "greet_formal": "आदरणीय {first_name},",
        "greet_email": "प्रिय {first_name},",
        "thanks": "{years} वर्षांपासून {bank} सोबत असल्याबद्दल धन्यवाद!",
        "thanks_new": "{bank} निवडल्याबद्दल धन्यवाद!",
        "loan": "आमचे {tier} ग्राहक म्हणून, तुमच्यासाठी ₹{amount} पर्यंतचे प्री-अप्रूव्ह्ड पर्सनल लोन उपलब्ध आहे — अंदाजे व्याजदर {rate}% प्रति वर्ष ({tenure} महिन्यांसाठी EMI सुमारे ₹{emi}/महिना).",
        "card": "आमचे {tier} ग्राहक म्हणून, तुम्ही ₹{amount} पर्यंत लिमिट असलेल्या {headline} साठी पात्र आहात.",
        "deposit": "आमचे {tier} ग्राहक म्हणून, तुम्ही आमचे {headline} {rate}% प्रति वर्ष{senior} दराने बुक करू शकता.",
        "investment": "आमचे {tier} ग्राहक म्हणून, तुम्ही फक्त ₹{amount}/महिना पासून {headline} सुरू करू शकता.",
        "senior": " (ज्येष्ठ नागरिक बोनस +{bonus}% सह)",
        "cta": "तपशीलांसाठी YES असे उत्तर द्या.",
        "cta_loan": "तपशीलांसाठी YES असे उत्तर द्या — रक्कम त्याच दिवशी तुमच्या खात्यात जमा होऊ शकते.",
        "cta_email": "या ईमेलला उत्तर द्या किंवा {rm_phone} वर कॉल करा, बाकी सर्व आम्ही पाहू.",
        "sign": "– {rm_name}, रिलेशनशिप मॅनेजर, {bank}",
        "sign_email": "धन्यवाद,\n{rm_name}\nरिलेशनशिप मॅनेजर, {bank}\n{rm_phone}",
        "subject_loan": "{first_name}, तुमची प्री-अप्रूव्ह्ड ऑफर तयार आहे",
        "subject_other": "{first_name}, {bank} कडून तुमच्यासाठी खास ऑफर",
    },
}

SMS_TEXT = {
    "English": "{bank}: Hi {first_name}, {sms_offer} Reply YES to know more.",
    "Hindi": "{bank}: नमस्ते {first_name} जी, {sms_offer} जानकारी के लिए YES भेजें।",
    "Marathi": "{bank}: नमस्कार {first_name}, {sms_offer} माहितीसाठी YES पाठवा.",
}
