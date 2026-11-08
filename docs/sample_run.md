# Sample run

LLM: `offline-rules` · data as of 2026-11-08


---

## Use case 1 – Personal-loan prospecting with personalised WhatsApp outreach


### 🧑‍💼 RM: Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.

<details><summary>Reasoning trace (9 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `search_customers` | Retrieve customers from CRM (filters: none) | Retrieved 300 of 300 customers (filters: none) |
| s2 | `analyze_transactions` | Derive behavioural signals from the last 90 days of transactions | Analysed 21,426 transactions for 300 customers over 90 days (as of 2026-11-08); 122 show big-ticket life-event spends, 122 show a balance dip ≥25% |
| s3 | `score_customer_value` | Keep high-value customers (value score ≥ 55) | 119/300 customers have value score ≥ 55 (Gold: 106, Platinum: 13) |
| s4 | `check_product_eligibility` | Apply Personal Loan credit-policy & contact rules | 65 eligible for Personal Loan, 54 rejected (top reasons – credit score: 37, already holds product: 14, age: 6, KYC pending: 6) |
| s5 | `score_conversion_propensity` | Estimate this month's conversion likelihood, keep ≥ 35%, rank top 10 | Scored 65 customers with logistic:personal_loan, held-out AUC 0.907; 25 ≥ 35% propensity, shortlisted 10 |
| s6 | `recommend_products` | Size an indicative Personal Loan offer and find the next-best cross-sell | Built offers for 10/10 customers; top cross-sell: Car Loan (5), Signature Rewards Credit Card (4) |
| s7 | `generate_outreach_messages` | Draft personalised whatsapp messages in each customer’s preferred language | Drafted 10 whatsapp messages (English, Hindi) via template |
| s8 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | 10/10 messages compliant & deliverable; 0 regenerated, 2 re-routed to a consented channel, 0 blocked (no consent) |
| s9 | `export_campaign` | Save CRM-ready campaign file | Exported 10 records → campaign_personal_loan_20261108_050558.csv |

</details>

### 🎯 Find high-value customers likely to take a Personal Loan this month and draft whatsapp outreach

**Funnel:** 300 customers scanned → 119 high-value → 65 eligible for Personal Loan → **10 shortlisted**

**Excluded by policy:** credit score (37), already holds product (14), age (6), KYC pending (6)

**Propensity model:** `logistic:personal_loan` · held-out AUC 0.907 on 3,000 past campaign outcomes

| # | Customer | City | Value | Propensity | Why now | Offer | Next best |
|---|---|---|---|---|---|---|---|
| 1 | Kunal Reddy (C0048) | Delhi | Platinum (80) | 86% | recent jump in spending, browsed loan pages in the app | ₹40,00,000 @ 11.25% | Signature Rewards Credit Card |
| 2 | Zoya Rao (C0057) | Delhi | Gold (69) | 90% | big-ticket life-event spending, recent jump in spending | ₹16,70,000 @ 11.25% | Signature Rewards Credit Card |
| 3 | Rahul Kapoor (C0191) | Delhi | Gold (58) | 94% | recent jump in spending, big-ticket life-event spending | ₹22,60,000 @ 11.25% | Home Loan |
| 4 | Neha Khan (C0076) | Hyderabad | Gold (66) | 87% | big-ticket life-event spending, recent jump in spending | ₹40,00,000 @ 10.49% | Car Loan |
| 5 | Komal Nair (C0125) | Pune | Gold (59) | 84% | big-ticket life-event spending, recent jump in spending | ₹16,10,000 @ 10.49% | Car Loan |
| 6 | Pranav Deshpande (C0051) | Kolkata | Gold (59) | 84% | recent jump in spending, big-ticket life-event spending | ₹11,20,000 @ 11.25% | Signature Rewards Credit Card |
| 7 | Fatima Singh (C0089) | Ahmedabad | Gold (70) | 74% | big-ticket life-event spending, recent jump in spending | ₹18,50,000 @ 11.25% | Signature Rewards Credit Card |
| 8 | Sakshi Nair (C0249) | Chennai | Gold (57) | 77% | big-ticket life-event spending, recent jump in spending | ₹15,60,000 @ 12.5% | Car Loan |
| 9 | Kunal Kapoor (C0179) | Ahmedabad | Gold (60) | 74% | recent jump in spending, browsed loan pages in the app | ₹16,10,000 @ 12.5% | Car Loan |
| 10 | Deepak Menon (C0158) | Ahmedabad | Gold (66) | 71% | recent jump in spending, browsed loan pages in the app | ₹36,30,000 @ 11.25% | Car Loan |

**Outreach:** 10 drafts · 10 compliant & deliverable · 2 re-routed to a consented channel

📁 Campaign file: `outputs/campaign_personal_loan_20261108_050558.csv`

_Try next:_ “Only show customers in Delhi” · “Why was Kunal Reddy selected?” · “Rewrite the messages in Hindi” · “Send them as email instead”

#### ✉️ Outreach messages

**Kunal Reddy** (C0048) · whatsapp · English · ✅ compliant · _template_
```text
Dear Mr. Reddy,

Thank you for banking with NovaBank for 11 years! As one of our Platinum customers, you have a pre-approved Personal Loan of up to ₹40,00,000 at an indicative 11.25% p.a. (EMI from about ₹1,31,429/month over 36 months).

Planning ahead for education? This can help you stay a step ahead.

Reply YES and I'll set it up — funds can reach your account the same day.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Zoya Rao** (C0057) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Zoya जी 🙏

11 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹16,70,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹54,872/माह)।

कोई बड़ा अपग्रेड प्लान कर रहे हैं? खर्च को आसान EMI में बांटें।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Rahul Kapoor** (C0191) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Rahul जी 🙏

3 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹22,60,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹74,257/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Neha Khan** (C0076) · whatsapp · English · ✅ compliant · _template_
```text
Dear Ms. Khan,

Thank you for banking with NovaBank for 2 years! As one of our Gold customers, you have a pre-approved Personal Loan of up to ₹40,00,000 at an indicative 10.49% p.a. (EMI from about ₹1,29,991/month over 36 months).

Eyeing a big upgrade? Spread the cost into easy EMIs.

Reply YES and I'll set it up — funds can reach your account the same day.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Komal Nair** (C0125) · email · English · ✅ compliant · _template_
```text
Subject: Komal, your pre-approved Personal Loan is ready

Dear Komal,

Thank you for banking with NovaBank for 8 years! As one of our Gold customers, you have a pre-approved Personal Loan of up to ₹16,10,000 at an indicative 10.49% p.a. (EMI from about ₹52,321/month over 36 months).

Eyeing a big upgrade? Spread the cost into easy EMIs. Simply reply to this email or call me on +91-98200-00000 and I'll take care of the rest.

Warm regards,
Ananya Iyer
Relationship Manager, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```
_notes: re-routed from whatsapp: no consent on that channel_

**Pranav Deshpande** (C0051) · whatsapp · English · ✅ compliant · _template_
```text
Hi Pranav 👋

Thank you for banking with NovaBank for 13 years! As one of our Gold customers, you have a pre-approved Personal Loan of up to ₹11,20,000 at an indicative 11.25% p.a. (EMI from about ₹36,800/month over 36 months).

Eyeing a big upgrade? Spread the cost into easy EMIs.

Reply YES and I'll set it up — funds can reach your account the same day.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Fatima Singh** (C0089) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Fatima जी 🙏

13 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹18,50,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹60,786/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Sakshi Nair** (C0249) · whatsapp · English · ✅ compliant · _template_
```text
Hi Sakshi 👋

Thank you for banking with NovaBank for 6 years! As one of our Gold customers, you have a pre-approved Personal Loan of up to ₹15,60,000 at an indicative 12.5% p.a. (EMI from about ₹52,188/month over 36 months).

Whether it's celebrations coming up or family plans, it helps you manage big expenses without touching your savings.

Reply YES and I'll set it up — funds can reach your account the same day.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Kunal Kapoor** (C0179) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Kunal जी 🙏

8 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹16,10,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 12.5% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹53,860/माह)।

अचानक आए खर्चों के लिए तुरंत फंड पाएं और अपनी बचत सुरक्षित रखें।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Deepak Menon** (C0158) · email · Hindi · ✅ compliant · _template_
```text
Subject: Deepak जी, आपका प्री-अप्रूव्ड ऑफ़र तैयार है

प्रिय Deepak जी,

NovaBank चुनने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹36,30,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹1,19,272/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है। बस इस ईमेल का जवाब दें या +91-98200-00000 पर कॉल करें, बाकी सब हम संभाल लेंगे।

सादर,
Ananya Iyer
रिलेशनशिप मैनेजर, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```
_notes: re-routed from whatsapp: no consent on that channel_


### 🧑‍💼 RM: Only show the ones in Delhi or Mumbai

<details><summary>Reasoning trace (9 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `search_customers` | Retrieve customers from CRM (filters: city in Delhi, Mumbai) | Retrieved 72 of 300 customers (filters: city in Delhi, Mumbai) |
| s2 | `analyze_transactions` | Derive behavioural signals from the last 90 days of transactions | Analysed 5,183 transactions for 72 customers over 90 days (as of 2026-11-08); 31 show big-ticket life-event spends, 31 show a balance dip ≥25% |
| s3 | `score_customer_value` | Keep high-value customers (value score ≥ 55) | 33/72 customers have value score ≥ 55 (Gold: 28, Platinum: 5) |
| s4 | `check_product_eligibility` | Apply Personal Loan credit-policy & contact rules | 15 eligible for Personal Loan, 18 rejected (top reasons – credit score: 12, already holds product: 5, KYC pending: 2, contact cool-down: 1) |
| s5 | `score_conversion_propensity` | Estimate this month's conversion likelihood, keep ≥ 35%, rank top 10 | Scored 15 customers with logistic:personal_loan, held-out AUC 0.907; 6 ≥ 35% propensity, shortlisted 6 |
| s6 | `recommend_products` | Size an indicative Personal Loan offer and find the next-best cross-sell | Built offers for 6/6 customers; top cross-sell: Signature Rewards Credit Card (4), Home Loan (1) |
| s7 | `generate_outreach_messages` | Draft personalised whatsapp messages in each customer’s preferred language | Drafted 6 whatsapp messages (English, Hindi) via template |
| s8 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | 6/6 messages compliant & deliverable; 0 regenerated, 1 re-routed to a consented channel, 0 blocked (no consent) |
| s9 | `export_campaign` | Save CRM-ready campaign file | Exported 6 records → campaign_personal_loan_20261108_050558.csv |

</details>

### 🎯 Find high-value customers likely to take a Personal Loan this month and draft whatsapp outreach

_Refined previous search · filters: city in Delhi, Mumbai_

**Funnel:** 72 customers scanned → 33 high-value → 15 eligible for Personal Loan → **6 shortlisted**

**Excluded by policy:** credit score (12), already holds product (5), KYC pending (2), contact cool-down (1)

**Propensity model:** `logistic:personal_loan` · held-out AUC 0.907 on 3,000 past campaign outcomes

| # | Customer | City | Value | Propensity | Why now | Offer | Next best |
|---|---|---|---|---|---|---|---|
| 1 | Kunal Reddy (C0048) | Delhi | Platinum (80) | 86% | recent jump in spending, browsed loan pages in the app | ₹40,00,000 @ 11.25% | Signature Rewards Credit Card |
| 2 | Zoya Rao (C0057) | Delhi | Gold (69) | 90% | big-ticket life-event spending, recent jump in spending | ₹16,70,000 @ 11.25% | Signature Rewards Credit Card |
| 3 | Rahul Kapoor (C0191) | Delhi | Gold (58) | 94% | recent jump in spending, big-ticket life-event spending | ₹22,60,000 @ 11.25% | Home Loan |
| 4 | Neha Rao (C0279) | Delhi | Platinum (76) | 40% | recent jump in spending, recent dip in account balance | ₹40,00,000 @ 12.5% | Signature Rewards Credit Card |
| 5 | Amit Kulkarni (C0170) | Mumbai | Gold (61) | 46% | recent jump in spending, big-ticket life-event spending | ₹24,20,000 @ 12.5% | Car Loan |
| 6 | Kunal Das (C0157) | Delhi | Gold (58) | 47% | browsed loan pages in the app, big-ticket life-event spending | ₹13,50,000 @ 10.49% | Signature Rewards Credit Card |

**Outreach:** 6 drafts · 6 compliant & deliverable · 1 re-routed to a consented channel

📁 Campaign file: `outputs/campaign_personal_loan_20261108_050558.csv`

_Try next:_ “Top 3 only” · “Why was Kunal Reddy selected?” · “Rewrite the messages in Hindi” · “Send them as email instead”

#### ✉️ Outreach messages

**Kunal Reddy** (C0048) · whatsapp · English · ✅ compliant · _template_
```text
Dear Mr. Reddy,

Thank you for banking with NovaBank for 11 years! As one of our Platinum customers, you have a pre-approved Personal Loan of up to ₹40,00,000 at an indicative 11.25% p.a. (EMI from about ₹1,31,429/month over 36 months).

Planning ahead for education? This can help you stay a step ahead.

Reply YES and I'll set it up — funds can reach your account the same day.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Zoya Rao** (C0057) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Zoya जी 🙏

11 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹16,70,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹54,872/माह)।

कोई बड़ा अपग्रेड प्लान कर रहे हैं? खर्च को आसान EMI में बांटें।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Rahul Kapoor** (C0191) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Rahul जी 🙏

3 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹22,60,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹74,257/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Neha Rao** (C0279) · email · English · ✅ compliant · _template_
```text
Subject: Neha, your pre-approved Personal Loan is ready

Dear Neha,

Thank you for banking with NovaBank for 16 years! As one of our Platinum customers, you have a pre-approved Personal Loan of up to ₹40,00,000 at an indicative 12.5% p.a. (EMI from about ₹1,33,815/month over 36 months).

If a big trip is on the cards, it can make the journey a lot easier. Simply reply to this email or call me on +91-98200-00000 and I'll take care of the rest.

Warm regards,
Ananya Iyer
Relationship Manager, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```
_notes: re-routed from whatsapp: no consent on that channel_

**Amit Kulkarni** (C0170) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Amit जी 🙏

3 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹24,20,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 12.5% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹80,958/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Kunal Das** (C0157) · whatsapp · English · ✅ compliant · _template_
```text
Hi Kunal 👋

Thank you for banking with NovaBank for 6 years! As one of our Gold customers, you have a pre-approved Personal Loan of up to ₹13,50,000 at an indicative 10.49% p.a. (EMI from about ₹43,872/month over 36 months).

Whether it's celebrations coming up or family plans, it helps you manage big expenses without touching your savings.

Reply YES and I'll set it up — funds can reach your account the same day.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```


### 🧑‍💼 RM: Rewrite the messages in Hindi

<details><summary>Reasoning trace (3 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `generate_outreach_messages` | Draft personalised whatsapp messages in Hindi | Drafted 6 whatsapp messages (Hindi) via template |
| s2 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | 6/6 messages compliant & deliverable; 0 regenerated, 1 re-routed to a consented channel, 0 blocked (no consent) |
| s3 | `export_campaign` | Save CRM-ready campaign file | Exported 6 records → campaign_personal_loan_20261108_050558.csv |

</details>

### ✉️ Draft whatsapp messages for the current shortlist of 6

6/6 messages are compliant and deliverable.

📁 Campaign file: `outputs/campaign_personal_loan_20261108_050558.csv`

#### ✉️ Outreach messages

**Kunal Reddy** (C0048) · whatsapp · Hindi · ✅ compliant · _template_
```text
आदरणीय Kunal जी,

11 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Platinum ग्राहक होने के नाते, आपके लिए ₹40,00,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹1,31,429/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Zoya Rao** (C0057) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Zoya जी 🙏

11 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹16,70,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹54,872/माह)।

कोई बड़ा अपग्रेड प्लान कर रहे हैं? खर्च को आसान EMI में बांटें।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Rahul Kapoor** (C0191) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Rahul जी 🙏

3 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹22,60,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 11.25% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹74,257/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Neha Rao** (C0279) · email · Hindi · ✅ compliant · _template_
```text
Subject: Neha जी, आपका प्री-अप्रूव्ड ऑफ़र तैयार है

प्रिय Neha जी,

16 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Platinum ग्राहक होने के नाते, आपके लिए ₹40,00,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 12.5% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹1,33,815/माह)।

अगर आप कोई बड़ी यात्रा प्लान कर रहे हैं, तो यह आपके सफ़र को आसान बना सकता है। बस इस ईमेल का जवाब दें या +91-98200-00000 पर कॉल करें, बाकी सब हम संभाल लेंगे।

सादर,
Ananya Iyer
रिलेशनशिप मैनेजर, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```
_notes: re-routed from whatsapp: no consent on that channel_

**Amit Kulkarni** (C0170) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Amit जी 🙏

3 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹24,20,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 12.5% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹80,958/माह)।

पढ़ाई से जुड़े खर्चों की योजना बना रहे हैं? यह आपके काम आ सकता है।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```

**Kunal Das** (C0157) · whatsapp · Hindi · ✅ compliant · _template_
```text
नमस्ते Kunal जी 🙏

6 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आपके लिए ₹13,50,000 तक का प्री-अप्रूव्ड पर्सनल लोन उपलब्ध है — सांकेतिक ब्याज दर 10.49% प्रति वर्ष (36 महीनों के लिए EMI लगभग ₹43,872/माह)।

शादी-ब्याह या पारिवारिक समारोह की तैयारी हो, आप अपनी बचत को छुए बिना बड़े खर्च आसानी से संभाल सकते हैं।

डिटेल्स के लिए YES लिखकर भेजें — पैसा उसी दिन आपके खाते में आ सकता है।

– Ananya Iyer, रिलेशनशिप मैनेजर, NovaBank

*T&C apply. Subject to credit approval. Reply STOP to opt out.
```


### 🧑‍💼 RM: Why was Kunal Reddy selected?

<details><summary>Reasoning trace (5 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `get_customer_profile` | Resolve customer 'Kunal Reddy' | Resolved 'Kunal Reddy' → C0048 Kunal Reddy |
| s2 | `analyze_transactions` | Recompute behavioural signals | Analysed 67 transactions for 1 customers over 90 days (as of 2026-11-08); 1 show big-ticket life-event spends, 1 show a balance dip ≥25% |
| s3 | `score_customer_value` | Recompute value score and its components | 1/1 customers have value score ≥ 0 (Platinum: 1) |
| s4 | `check_product_eligibility` | Re-check Personal Loan policy rules | 1 eligible for Personal Loan, 0 rejected |
| s5 | `score_conversion_propensity` | Recompute propensity with feature-level contributions | Scored 1 customers with logistic:personal_loan, held-out AUC 0.907; 1 ≥ 0% propensity, shortlisted 1 |

</details>

### 🔍 Why Kunal Reddy (C0048) for Personal Loan?

**Value:** Platinum (80/100) – components: income 0.99, balance 0.73, relationship 0.73, product_depth 0.50, engagement 0.71

**Conversion propensity this month:** 86% (`logistic:personal_loan`) → ranked **#1** in the current shortlist

**Positive drivers:** recent jump in spending, browsed loan pages in the app, big-ticket life-event spending

**Holding back:** irregular income credits, not salaried

**Policy check:** ✅ eligible

**Last 90 days (RM-internal, never shown to customer):** monthly spend ≈ ₹4,78,807, spend change +250%, big-ticket spends ₹8,97,142 (education), balance dip 54%, EMI/income 0%

| Feature | Contribution |
|---|---|
| spend_growth | +1.33 |
| loan_page_visits_norm | +1.04 |
| life_event_ratio | +0.59 |
| balance_dip | +0.34 |
| dti | +0.32 |
| relationship_norm | +0.17 |


---

## Use case 2 – Credit-card upgrade campaign, then switch channel


### 🧑‍💼 RM: Which salaried customers should get a credit card upgrade? Top 5

<details><summary>Reasoning trace (6 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `search_customers` | Retrieve customers from CRM (filters: employment salaried) | Retrieved 200 of 300 customers (filters: employment salaried) |
| s2 | `analyze_transactions` | Derive behavioural signals from the last 90 days of transactions | Analysed 13,781 transactions for 200 customers over 90 days (as of 2026-11-08); 79 show big-ticket life-event spends, 79 show a balance dip ≥25% |
| s3 | `score_customer_value` | Keep high-value customers (value score ≥ 55) | 73/200 customers have value score ≥ 55 (Gold: 65, Platinum: 8) |
| s4 | `check_product_eligibility` | Apply Signature Rewards Credit Card credit-policy & contact rules | 31 eligible for Signature Rewards Credit Card, 42 rejected (top reasons – credit score: 29, already holds product: 14, KYC pending: 3, contact cool-down: 1) |
| s5 | `score_conversion_propensity` | Estimate this month's conversion likelihood, keep ≥ 35%, rank top 5 | Scored 31 customers with heuristic:credit_card_premium; 31 ≥ 35% propensity, shortlisted 5 |
| s6 | `recommend_products` | Size an indicative Signature Rewards Credit Card offer and find the next-best cross-sell | Built offers for 5/5 customers; top cross-sell: Car Loan (3), Personal Loan (1) |

</details>

### 🎯 Find high-value customers likely to take a Signature Rewards Credit Card this month

**Funnel:** 200 customers scanned → 73 high-value → 31 eligible for Signature Rewards Credit Card → **5 shortlisted**

**Excluded by policy:** credit score (29), already holds product (14), KYC pending (3), contact cool-down (1)

**Propensity model:** `heuristic:credit_card_premium` · transparent signal weights (no campaign history yet)

| # | Customer | City | Value | Propensity | Why now | Offer | Next best |
|---|---|---|---|---|---|---|---|
| 1 | Fatima Singh (C0089) | Ahmedabad | Gold (70) | 87% | frequent dining spends, high online shopping | limit ₹4,90,000 | Car Loan |
| 2 | Zoya Rao (C0057) | Delhi | Gold (69) | 88% | frequent dining spends, high online shopping | limit ₹3,40,000 | Personal Loan |
| 3 | Kunal Reddy (C0048) | Delhi | Platinum (80) | 82% | high online shopping, high monthly card/UPI spend | limit ₹10,00,000 | Car Loan |
| 4 | Sanjay Kulkarni (C0023) | Mumbai | Platinum (85) | 79% | frequent dining spends, high online shopping | limit ₹10,00,000 | Home Loan |
| 5 | Komal Nair (C0125) | Pune | Gold (59) | 89% | frequent dining spends, high online shopping | limit ₹3,30,000 | Car Loan |

_Try next:_ “Only show customers in Ahmedabad” · “Why was Fatima selected?” · “Generate WhatsApp messages for them” · “Export this campaign”


### 🧑‍💼 RM: Send them as email instead

<details><summary>Reasoning trace (3 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `generate_outreach_messages` | Draft personalised email messages in each customer’s preferred language | Drafted 5 email messages (English, Hindi, Marathi) via template |
| s2 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | 5/5 messages compliant & deliverable; 0 regenerated, 0 re-routed to a consented channel, 0 blocked (no consent) |
| s3 | `export_campaign` | Save CRM-ready campaign file | Exported 5 records → campaign_credit_card_premium_20261108_050558.csv |

</details>

### ✉️ Draft email messages for the current shortlist of 5

5/5 messages are compliant and deliverable.

📁 Campaign file: `outputs/campaign_credit_card_premium_20261108_050558.csv`

#### ✉️ Outreach messages

**Fatima Singh** (C0089) · email · Hindi · ✅ compliant · _template_
```text
Subject: Fatima जी, NovaBank की ओर से आपके लिए खास ऑफ़र

प्रिय Fatima जी,

13 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आप ₹4,90,000 तक की लिमिट वाले lifetime-free Signature Rewards Credit Card के लिए पात्र हैं।

हर बार बाहर खाने पर ज़्यादा रिवॉर्ड्स पाएं। बस इस ईमेल का जवाब दें या +91-98200-00000 पर कॉल करें, बाकी सब हम संभाल लेंगे।

सादर,
Ananya Iyer
रिलेशनशिप मैनेजर, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```

**Zoya Rao** (C0057) · email · Hindi · ✅ compliant · _template_
```text
Subject: Zoya जी, NovaBank की ओर से आपके लिए खास ऑफ़र

प्रिय Zoya जी,

11 साल से NovaBank के साथ बने रहने के लिए धन्यवाद! हमारे Gold ग्राहक होने के नाते, आप ₹3,40,000 तक की लिमिट वाले lifetime-free Signature Rewards Credit Card के लिए पात्र हैं।

हर बार बाहर खाने पर ज़्यादा रिवॉर्ड्स पाएं। बस इस ईमेल का जवाब दें या +91-98200-00000 पर कॉल करें, बाकी सब हम संभाल लेंगे।

सादर,
Ananya Iyer
रिलेशनशिप मैनेजर, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```

**Kunal Reddy** (C0048) · email · English · ✅ compliant · _template_
```text
Subject: Kunal, an exclusive offer for you from NovaBank

Dear Kunal,

Thank you for banking with NovaBank for 11 years! As one of our Platinum customers, you're eligible for our lifetime-free Signature Rewards Credit Card with a credit limit of up to ₹10,00,000.

Earn accelerated rewards on your online shopping. Simply reply to this email or call me on +91-98200-00000 and I'll take care of the rest.

Warm regards,
Ananya Iyer
Relationship Manager, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```

**Sanjay Kulkarni** (C0023) · email · Marathi · ✅ compliant · _template_
```text
Subject: Sanjay, NovaBank कडून तुमच्यासाठी खास ऑफर

प्रिय Sanjay,

13 वर्षांपासून NovaBank सोबत असल्याबद्दल धन्यवाद! आमचे Platinum ग्राहक म्हणून, तुम्ही ₹10,00,000 पर्यंत लिमिट असलेल्या lifetime-free Signature Rewards Credit Card साठी पात्र आहात.

प्रत्येक वेळी बाहेर जेवताना जास्त रिवॉर्ड्स मिळवा. या ईमेलला उत्तर द्या किंवा +91-98200-00000 वर कॉल करा, बाकी सर्व आम्ही पाहू.

धन्यवाद,
Ananya Iyer
रिलेशनशिप मॅनेजर, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```

**Komal Nair** (C0125) · email · English · ✅ compliant · _template_
```text
Subject: Komal, an exclusive offer for you from NovaBank

Dear Komal,

Thank you for banking with NovaBank for 8 years! As one of our Gold customers, you're eligible for our lifetime-free Signature Rewards Credit Card with a credit limit of up to ₹3,30,000.

Enjoy accelerated rewards every time you dine out. Simply reply to this email or call me on +91-98200-00000 and I'll take care of the rest.

Warm regards,
Ananya Iyer
Relationship Manager, NovaBank
+91-98200-00000

T&C apply. Subject to credit approval.
To unsubscribe from marketing emails, reply UNSUBSCRIBE.
```


### 🧑‍💼 RM: Export this campaign

<details><summary>Reasoning trace (1 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `export_campaign` | Write CSV/JSON for CRM upload | Exported 5 records → campaign_credit_card_premium_20261108_050558.csv |

</details>

📁 Exported the current campaign:

- `outputs/campaign_credit_card_premium_20261108_050558.csv`
- `outputs/campaign_credit_card_premium_20261108_050558.json`


---

## Use case 3 – Customer 360, explainability and self-correction


### 🧑‍💼 RM: Tell me about C0042

<details><summary>Reasoning trace (4 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `get_customer_profile` | Resolve customer 'C0042' | Resolved 'C0042' → C0042 Abhishek Pillai |
| s2 | `analyze_transactions` | Summarise recent financial behaviour | Analysed 73 transactions for 1 customers over 90 days (as of 2026-11-08); 0 show big-ticket life-event spends, 0 show a balance dip ≥25% |
| s3 | `score_customer_value` | Score customer value | 1/1 customers have value score ≥ 0 (Silver: 1) |
| s4 | `recommend_products` | Recommend the best-fit products across the catalogue | Built offers for 1/1 customers; top cross-sell: Car Loan (1) |

</details>

### 👤 Abhishek Pillai (C0042)

48 · Data Analyst (salaried) · Chennai · prefers English

**Segment:** Mass · **Value:** Silver (42) · **Tenure:** 5.7 yrs · **Credit score:** 775 · **Income:** ₹7,72,000/yr

**Holds:** savings account

**Consented channels:** WhatsApp, SMS, Email

**Recent behaviour:** spend ≈ ₹43,307/mo (-10% last 30d), top categories groceries, shopping, dining

**Best-fit product:** Signature Rewards Credit Card (limit ₹1,90,000) · next: Car Loan


### 🧑‍💼 RM: Find fixed deposit prospects among retirees in Chennai and draft SMS messages

<details><summary>Reasoning trace (29 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `search_customers` | Retrieve customers from CRM (filters: city in Chennai; employment retired) | Retrieved 2 of 300 customers (filters: city in Chennai; employment retired) |
| s2 | `analyze_transactions` | Derive behavioural signals from the last 90 days of transactions | Analysed 128 transactions for 2 customers over 90 days (as of 2026-11-08); 0 show big-ticket life-event spends, 0 show a balance dip ≥25% |
| s3 | `score_customer_value` | Keep high-value customers (value score ≥ 55) | 0/2 customers have value score ≥ 55 |
| s4 | `check_product_eligibility` | Apply High-Yield Fixed Deposit credit-policy & contact rules | skipped – no candidates left to act on |
| s5 | `score_conversion_propensity` | Estimate this month's conversion likelihood, keep ≥ 35%, rank top 10 | skipped – no candidates left to act on |
| s6 | `recommend_products` | Size an indicative High-Yield Fixed Deposit offer and find the next-best cross-sell | skipped – no candidates left to act on |
| s7 | `generate_outreach_messages` | Draft personalised sms messages in each customer’s preferred language | skipped – no candidates left to act on |
| s8 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | skipped – no candidates left to act on |
| s9 | `export_campaign` | Save CRM-ready campaign file | skipped – no candidates left to act on |
| reflect1 | `reflection` | Self-check on empty result | No customers passed the high-value cut-off (55); relaxed it to 40 and re-ran the plan. |
| r1.s1 | `search_customers` | Retrieve customers from CRM (filters: city in Chennai; employment retired) | Retrieved 2 of 300 customers (filters: city in Chennai; employment retired) |
| r1.s2 | `analyze_transactions` | Derive behavioural signals from the last 90 days of transactions | Analysed 128 transactions for 2 customers over 90 days (as of 2026-11-08); 0 show big-ticket life-event spends, 0 show a balance dip ≥25% |
| r1.s3 | `score_customer_value` | Keep high-value customers (value score ≥ 40) | 0/2 customers have value score ≥ 40 |
| r1.s4 | `check_product_eligibility` | Apply High-Yield Fixed Deposit credit-policy & contact rules | skipped – no candidates left to act on |
| r1.s5 | `score_conversion_propensity` | Estimate this month's conversion likelihood, keep ≥ 35%, rank top 10 | skipped – no candidates left to act on |
| r1.s6 | `recommend_products` | Size an indicative High-Yield Fixed Deposit offer and find the next-best cross-sell | skipped – no candidates left to act on |
| r1.s7 | `generate_outreach_messages` | Draft personalised sms messages in each customer’s preferred language | skipped – no candidates left to act on |
| r1.s8 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | skipped – no candidates left to act on |
| r1.s9 | `export_campaign` | Save CRM-ready campaign file | skipped – no candidates left to act on |
| reflect2 | `reflection` | Self-check on empty result | No customers passed the high-value cut-off (40); relaxed it to 25 and re-ran the plan. |
| r2.s1 | `search_customers` | Retrieve customers from CRM (filters: city in Chennai; employment retired) | Retrieved 2 of 300 customers (filters: city in Chennai; employment retired) |
| r2.s2 | `analyze_transactions` | Derive behavioural signals from the last 90 days of transactions | Analysed 128 transactions for 2 customers over 90 days (as of 2026-11-08); 0 show big-ticket life-event spends, 0 show a balance dip ≥25% |
| r2.s3 | `score_customer_value` | Keep high-value customers (value score ≥ 25) | 2/2 customers have value score ≥ 25 (Standard: 2) |
| r2.s4 | `check_product_eligibility` | Apply High-Yield Fixed Deposit credit-policy & contact rules | 2 eligible for High-Yield Fixed Deposit, 0 rejected |
| r2.s5 | `score_conversion_propensity` | Estimate this month's conversion likelihood, keep ≥ 35%, rank top 10 | Scored 2 customers with heuristic:fixed_deposit; 2 ≥ 35% propensity, shortlisted 2 |
| r2.s6 | `recommend_products` | Size an indicative High-Yield Fixed Deposit offer and find the next-best cross-sell | Built offers for 2/2 customers; top cross-sell: Mutual Fund SIP (2) |
| r2.s7 | `generate_outreach_messages` | Draft personalised sms messages in each customer’s preferred language | Drafted 2 sms messages (English) via template |
| r2.s8 | `check_message_compliance` | Validate consent, disclaimers, claims & PII; repair or re-route | 2/2 messages compliant & deliverable; 0 regenerated, 1 re-routed to a consented channel, 0 blocked (no consent) |
| r2.s9 | `export_campaign` | Save CRM-ready campaign file | Exported 2 records → campaign_fixed_deposit_20261108_050558.csv |

</details>

### 🎯 Find high-value customers likely to take a High-Yield Fixed Deposit this month and draft sms outreach

**Funnel:** 2 customers scanned → 2 high-value → 2 eligible for High-Yield Fixed Deposit → **2 shortlisted**

**Propensity model:** `heuristic:fixed_deposit` · transparent signal weights (no campaign history yet)

> ℹ️ No customers passed the high-value cut-off (55); relaxed it to 40 and re-ran the plan.

> ℹ️ No customers passed the high-value cut-off (40); relaxed it to 25 and re-ran the plan.

| # | Customer | City | Value | Propensity | Why now | Offer | Next best |
|---|---|---|---|---|---|---|---|
| 1 | Aarav Agarwal (C0091) | Chennai | Standard (32) | 91% | large idle balance, senior citizen (bonus rate) | 7.9% p.a. | Mutual Fund SIP |
| 2 | Tanvi Bhat (C0124) | Chennai | Standard (28) | 71% | large idle balance, senior citizen (bonus rate) | 7.9% p.a. | Mutual Fund SIP |

**Outreach:** 2 drafts · 2 compliant & deliverable · 1 re-routed to a consented channel

📁 Campaign file: `outputs/campaign_fixed_deposit_20261108_050558.csv`

_Try next:_ “Top 3 only” · “Why was Aarav selected?” · “Rewrite the messages in Hindi” · “Send them as email instead”

#### ✉️ Outreach messages

**Aarav Agarwal** (C0091) · whatsapp · English · ✅ compliant · _template_
```text
Hi Aarav 👋

Thank you for banking with NovaBank for 6 years! As one of our Standard customers, you can lock in our High-Yield Fixed Deposit at 7.9% p.a. (includes a +0.5% senior-citizen bonus).

It's an easy way to make your idle savings work harder.

Reply YES and I'll set it up for you.

– Ananya Iyer, your Relationship Manager, NovaBank

*T&C apply. Reply STOP to opt out.
```
_notes: re-routed from sms: no consent on that channel_

**Tanvi Bhat** (C0124) · sms · English · ✅ compliant · _template_
```text
NovaBank: Hi Tanvi, our High-Yield Fixed Deposit @ 7.9% p.a. is now open for you. Reply YES to know more. T&C apply. Reply STOP to opt out.
```
_notes: Tamil template unavailable offline – used English (configure an LLM for Tamil)._


### 🧑‍💼 RM: What products do we have?

<details><summary>Reasoning trace (1 steps)</summary>

| step | tool | why | result |
|---|---|---|---|
| s1 | `list_products` | Read product catalogue | 6 products in catalogue |

</details>

### 🏦 Product catalogue

| Product | Category | Min income | Min score | Age | Model |
|---|---|---|---|---|---|
| Personal Loan (`personal_loan`) | lending | ₹3,00,000 | 700 | 21-58 | `logistic:personal_loan` |
| Signature Rewards Credit Card (`credit_card_premium`) | cards | ₹6,00,000 | 720 | 21-65 | `heuristic:credit_card_premium` |
| Home Loan (`home_loan`) | lending | ₹8,00,000 | 720 | 23-55 | `heuristic:home_loan` |
| Car Loan (`auto_loan`) | lending | ₹4,00,000 | 700 | 21-60 | `heuristic:auto_loan` |
| High-Yield Fixed Deposit (`fixed_deposit`) | deposits | ₹0 | 0 | 18-100 | `heuristic:fixed_deposit` |
| Mutual Fund SIP (`mutual_fund_sip`) | investments | ₹3,00,000 | 0 | 18-70 | `heuristic:mutual_fund_sip` |
