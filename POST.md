# Arabic

بنيت CopyLedger للتحقق من نسخ المجلدات: ينشئ إيصال SHA-256 للملفات، ثم يقارن النسخة ويكشف الناقص والمختلف والإضافي، حتى لو الملف تغيّر ومقاسه بقي نفسه.

ويقترح انتقال ملف إلى مسار جديد عند وجود تطابق محتوى واحد واضح، دون إعادة تسمية أو حذف أي شيء. يعمل محليًا دون مكتبات خارجية، مع تقرير HTML وتجربة اصطناعية و18 اختبارًا ناجحًا.

https://github.com/dxrkf/copyledger

#Python #Backup #FileIntegrity #DeveloperTools

# English

Introducing CopyLedger: an offline, zero-dependency Python CLI for folder-copy verification using SHA256 content receipts.

Find missing, changed and extra files—including same-size changes—and review unambiguous possible moves without modifying the folders. Includes JSON/HTML reports, a reproducible synthetic demo and 18 passing tests.

Receipts verify bytes against a supplied baseline; they are not signatures or replacements for backups.

https://github.com/dxrkf/copyledger

Attach assets/cover.png and assets/demo-output.png. Only synthetic filenames are included in these assets.
