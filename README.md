# Neel — Telegram Video Mini App + Bot

Private-channel video storage, bot-only uploads, premium blue Mini App (dark + light), Oxapay USDT subscriptions,
sharded MongoDB, multi-admin panel, dynamic watermark and anti-recording measures.

## सेटअप (Setup)
1. **BotFather**: बॉट बनाइए → token लीजिए। `/newapp` से Mini App बनाइए (URL = आपकी Render URL) और उसका *short name* `MINIAPP_SHORT` में डालिए।
2. **my.telegram.org** से `API_ID` और `API_HASH` लीजिए (बड़े वीडियो स्ट्रीम करने के लिए ज़रूरी)।
3. **Private channel** बनाइए (वीडियो स्टोरेज) → बॉट को **admin** बनाइए → उसकी ID (`-100…`) `STORAGE_CHANNEL_ID` में डालिए।
4. **Update channel** (force-join) → बॉट को वहाँ भी admin बनाइए → `UPDATE_CHANNEL=@name`।
5. **MongoDB**: हर shard अलग cluster (जैसे Atlas free) → URIs `;` से अलग करके `MONGO_URIS` में डालिए। Atlas में Network Access `0.0.0.0/0` रखिए।
6. **Oxapay**: merchant API key `OXAPAY_KEY` में। Callback अपने-आप `WEBAPP_URL/webhook/oxapay` सेट होता है।
7. `.env.example` को `.env` बनाइए (Render में इन्हें Environment Variables में डालिए) और deploy कीजिए:
   `pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000`
8. **Images बदलिए (ज़रूरी)**: `app/static/img/welcome.jpg` और `upsell.jpg` (16:9, ~1280×720)।

## उपयोग
- **Upload**: बॉट में `/admin` → *Upload video* → ① वीडियो ② थंबनेल ③ टाइटल → preview → **Publish** बटन। तुरंत Mini App में दिखता है, और सबको push notification जाता है।
- **Admin panel**: बॉट में `/admin` → *Admin panel*। Admin का कोई बटन/संकेत सामान्य यूज़र को नहीं दिखता (non-admin के लिए API 404 देती है)।
- **Roles**: owner (`SUPER_ADMIN_IDS`), admin, uploader, support। Owner पैनल से बाकी admins जोड़ता है।
- **Share link**: `https://t.me/<bot>/<MINIAPP_SHORT>?startapp=v_<id>` — Mini App के अंदर सीधे उसी वीडियो पर खुलता है।
- **Sharding**: videos/views active shard पर लिखे जाते हैं। `SHARD_MAX_MB` भरते ही अगले shard पर अपने-आप switch होता है (owners को मैसेज जाता है)। users/payments/admins पहले cluster में रहते हैं।
- **Force join**: बॉट `/start` और Mini App खुलते ही update channel join करने का popup आता है।

## Security — सीमाएँ ईमानदारी से
- पूरी तरह anti-recording संभव नहीं (फोन कैमरा/OS स्क्रीन रिकॉर्डर नहीं रोके जा सकते)। यह सिस्टम इन्हें करता है: user-specific चलता हुआ वॉटरमार्क (tamper होने पर प्लेबैक रुकता है), ऐप background/blur होने पर pause, PrintScreen/DevTools/right-click ब्लॉक, download/PiP बंद, signed stream token (3 घंटे, user-bound, max 2 डिवाइस), बॉट के संदेशों पर `protect_content`।
- वॉटरमार्क ब्राउज़र में ओवरले है (वीडियो में burn नहीं होता)। Burned-in के लिए ffmpeg re-encode चाहिए।
- वीडियो MTProto (Pyrogram) से स्ट्रीम होते हैं; ब्राउज़र के लिए mp4 (H.264) सबसे बेहतर चलता है, mkv आदि कुछ डिवाइस पर नहीं चलेंगे।
- Live viewers और sessions memory में हैं → **एक ही instance** चलाइए (polling भी एक ही instance पर)।
- Render free plan सो जाता है; बॉट polling के लिए paid/always-on instance या UptimeRobot ping `/health` रखिए।
