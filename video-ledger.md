# دفتر حساب — TED-Ed German

کانال: https://www.youtube.com/@TEDEdGerman

ویدیوی بعدی با `python3 scripts/fetch.py next` تعیین می‌شود: تازه‌ترین ویدیوی کانال که شناسه‌اش در این دفتر نیست.
اگر ویدیوی تازه‌ای آپلود نشده باشد، نتیجه همان ویدیوی بعدیِ پردازش‌نشده در آرشیو است.

**فقط شناسهٔ ویدیو (`videoId`) داخل بک‌تیک بیاید**؛ اسکریپت هر عبارت ۱۱‌نویسهٔ داخل بک‌تیک را شناسهٔ ویدیو حساب می‌کند.

## پردازش‌شده‌ها

| # | videoId | عنوان | انتشار | پردازش | واحد | ردیف کلمه |
|---|---------|-------|--------|--------|------|-----------|
| ۱ | `-8OTA0---K4` | Der Aufstieg und Fall des assyrischen Reiches | 2026-09-18 | 2026-09-21 | ۷۳ | ۶۳۵ |
| ۲ | `Wo7rUJNVPYs` | Kannst du das Spindrätsel lösen? | 2026-09-16 | 2026-09-22 | ۷۰ | ۴۹۸ |

## یادداشت‌ها

- **ویدیوی ۱ — اصلاح‌های متن** (زیرنویس ترجمه‌ای و پر از غلط بود؛ همهٔ این‌ها در `transcripts/-8OTA0---K4.txt` اعمال شده):
  - `über den britischen Empire` → `über dem britischen Empire`
  - `Jinges Kahn` → `Dschingis Khan`
  - `Aschu` / `Ash` (نام شهر) → `Assur`؛ `Ashur Ubali I.` → `Assur-uballit I.`
  - `administrativden denkenden` → `administrativ denkenden`
  - `Assyer` (۳ بار) → `Assyrer`
  - `Belagerungstaktiken an. und bestraften` → `… an und bestraften` (نقطهٔ اضافی)
  - `Pfehlen und Heuten` → `Pfählen und Häuten`
  - `Shamuramat` → `Schammuramat`؛ `Niniwe` → `Ninive` (هم‌شکل با جای دیگر متن)
  - `Ash Bunny Apli` و `As Bunny Applis` → `Assurbanipal` و `Assurbanipals`
  - `Arkadisch und Somerisch` → `Akkadisch und Sumerisch`
  - `Gilgamescheppos` → `Gilgamesch-Epos`
  - `den Babylon und Medern` → `den Babyloniern und Medern`
  - `Vorreiter, das bis zum` → `Vorreiter, was bis zum`
  - یک نکتهٔ دستوری مشکوک ولی دست‌نخورده: `verloren die Assyrer durch …, einen Großteil …` (ویرگولِ اضافه پیش از `einen Großteil`).

- **ویدیوی ۲ — اصلاح‌های متن** (در `transcripts/Wo7rUJNVPYs.txt` اعمال شده):
  - حذف سرسطرِ زیرنویس `Übersetzung: Anja Alongi Lektorat: Alexandra Köster` از ابتدای متن (جزو گفتار ویدیو نیست).
  - `gleich die Anzahl der Teiler` → `gleich der Anzahl der Teiler` (صفتِ `gleich` مکملش را datif می‌گیرد).
  - دست‌نخورده‌ها: `der Spindnummern` (جمع، در حالی که منطقاً شمارهٔ همان یک کمد است) و `Denn` در آغاز جملهٔ `Denn die einzigen Spinde …` (تکرار حرف ربط پس از `denn` در جملهٔ پیش)؛ هیچ‌کدام غلط آشکار نیستند.

- **محیط ساخت (۲۰۲۶-۰۹-۲۲):** برای اجرای `drill.py build` روی این دستگاه لازم شد: `piper-tts` (پایتون ۳.۱۴)، مدل صدای `de_DE-thorsten-medium` در `~/.cache/piper-voices/`، و `ffmpeg.exe` + `node.exe` در `C:\Users\FATEMEH\bin` (این پوشه در PATH نیست؛ هنگام build باید به PATH اضافه شود). onnxruntime بدون `msvcp140_1.dll` و نسخهٔ تازهٔ `msvcp140.dll` بالا نمی‌آمد؛ این DLLها کنار `onnxruntime/capi/` کپی شدند. راه‌حل تمیزتر: نصب Visual C++ Redistributable 2015-2022 x64.
