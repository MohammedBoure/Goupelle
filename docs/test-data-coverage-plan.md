# خطة تغطية اختبارات البيانات في Goupelle

## نطاق الفحص

هذه الخطة تغطي أماكن حفظ البيانات وعرضها للمستخدم في الملفات التالية:

- `label_config.json`: ملف إعدادات الملصق والطابعة والعناصر المرئية.
- `print_history.db`: قاعدة SQLite لسجل الطباعة.
- `database.py`: إنشاء قاعدة البيانات وحفظ/قراءة سجلات الطباعة.
- `ui/main_dialog.py`: إدخال الوزن والعيار، الحسابات الحية، بناء الملصق، وحفظ سجل الطباعة.
- `ui/settings_dialog.py`: قراءة/حفظ إعدادات الملصق ومعاينة العناصر.
- `ui/history_dialog.py`: عرض سجل الطباعة، البحث، الصفحات، وتفاصيل السجل.

يجب ألا تستخدم الاختبارات الملفين الحقيقيين `label_config.json` و `print_history.db`. كل اختبار يجب أن يستخدم `tmp_path` أو مجلد مؤقت مثل `tests/tmp`.

## خريطة حفظ البيانات

### إعدادات الملصق

- الحفظ يتم في `SettingsDialog.save_config`.
- القراءة تتم في `SettingsDialog.load_config` و `MainPrintDialog.load_config`.
- المسار الافتراضي الحالي هو `label_config.json` عبر `self.config_file`.
- البيانات المهمة:
  - `printer_name`
  - `label_width_mm`, `label_height_mm`, `gap_mm`
  - `offset_x_mm`, `offset_y_mm`, `orientation`
  - `logo` و `logo_settings`
  - `elements` لكل عنصر مرئي:
    - `show`
    - `text`
    - `x`, `y`
    - `size`
    - `font`
    - `angle`
  - عناصر التحويل في الملصق:
    - `conv_gold_730`
    - `conv_gold_750`
    - `conv_silver_925`
    - `conv_silver_9999`
  - خيارات ظهور `equiv_weight`:
    - `show_for_gold`
    - `show_for_silver`

### سجل الطباعة

- إنشاء الجدول يتم في `database.init_db`.
- حفظ سجل جديد يتم في `database.save_print_record`.
- القراءة حسب الفترة تتم في `database.get_records_by_date_range`.
- قراءة سجل محدد تتم في `database.get_record_by_id`.
- الواجهة تقرأ مباشرة من SQLite في `HistoryDialog.load_data`.
- اسم ملف القاعدة الافتراضي موجود مرتين:
  - `database.DB_FILE`
  - `ui.history_dialog.DB_FILE`

## خريطة عرض البيانات

### الواجهة الرئيسية

- إدخال المستخدم:
  - `weight_input`
  - `gold_input`
  - `silver_input`
- العرض الحي:
  - `lbl_live_title`
  - `lbl_live_equiv`
  - `extra_conversion_labels`
- منطق الحساب:
  - الذهب الأساسي يستخدم مرجع `ref_gold` الافتراضي `730`.
  - الفضة الأساسية تستخدم مرجع `ref_silver` الافتراضي `925`.
  - التحويلات الإضافية الحية تعرض:
    - الذهب: `750`
    - الفضة: `999.9`
- الملصق المطبوع يبني النصوص من `elements` ويضيف:
  - رقم السجل
  - المعدن
  - العيار
  - الوزن
  - الوزن المحول
  - التحويلات المحددة حسب المعدن
  - التاريخ

### نافذة الإعدادات

- تعرض حقول الطابعة والورق والشعار.
- تعرض صفوف عناصر الملصق، وكل صف يحتوي:
  - مربع تفعيل `show`
  - حقل بادئة النص `text`
  - موضع وحجم وخط وزاوية.
- تعرض معاينة مباشرة عبر `get_pil_image` و `generate_preview`.
- يجب التأكد أن قسم `العيار المرجعي للتحويل` غير موجود في الواجهة.

### نافذة السجل

- تعرض الجدول بخمسة أعمدة:
  - `ID`
  - التاريخ والوقت
  - المعدن
  - العيار
  - الوزن الفعلي
- تحفظ الصف الكامل في `Qt.UserRole` لعرض التفاصيل.
- تعرض التفاصيل:
  - ID
  - تاريخ الطباعة
  - نوع المعدن
  - العيار الفعلي
  - الوزن الفعلي
  - الوزن المحول
  - اسم الطابعة

## قواعد العزل في الاختبارات

- لا تفتح أو تعدل `label_config.json` الحقيقي.
- لا تفتح أو تعدل `print_history.db` الحقيقي.
- استخدم `tmp_path / "label_config.json"` مع:
  - `dialog.config_file = str(temp_config)`
  - ثم إعادة `load_config` أو إنشاء كائن جديد مضبوط.
- استخدم `tmp_path / "print_history.db"` مع:
  - `monkeypatch.setattr(database, "DB_FILE", str(temp_db))`
  - `monkeypatch.setattr(ui.history_dialog, "DB_FILE", str(temp_db))`
- اختبارات الواجهة تحتاج `QApplication` واحدة في fixture.
- اختبارات الطباعة يجب أن تمنع الطباعة الفعلية عبر monkeypatch:
  - `win32print.OpenPrinter`
  - `win32print.WritePrinter`
  - أو اختبار بناء الصورة/الحسابات دون الوصول للطابعة.
- اختبارات الرسائل يجب أن تمنع popups عبر monkeypatch:
  - `QMessageBox.information`
  - `QMessageBox.warning`
  - `QMessageBox.critical`

## خطة الاختبارات

### 1. اختبارات قاعدة البيانات

ملف مقترح: `tests/test_database.py`

- `test_init_db_creates_printed_labels_table`
  - استخدم قاعدة مؤقتة.
  - استدع `init_db`.
  - تحقق أن جدول `printed_labels` موجود بالأعمدة المتوقعة.

- `test_save_print_record_returns_new_id_and_persists_values`
  - احفظ سجل ذهب.
  - تحقق أن ID رقم صحيح.
  - اقرأ الصف من SQLite وتحقق من `metal_type`, `actual_purity`, `actual_weight`, `equivalent_weight`, `printer_name`.

- `test_get_record_by_id_returns_exact_record`
  - احفظ سجلين.
  - اقرأ السجل الثاني بالـ ID.
  - تحقق أن البيانات لا تختلط بين السجلات.

- `test_get_records_by_date_range_filters_and_orders_desc`
  - أدخل سجلات بتواريخ مختلفة مباشرة في SQLite.
  - استدع `get_records_by_date_range`.
  - تحقق أن النتائج داخل الفترة فقط ومرتبة تنازليًا.

- `test_empty_database_returns_empty_lists`
  - أنشئ القاعدة بدون بيانات.
  - تحقق أن القراءة ترجع قائمة فارغة وأن البحث عن ID غير موجود يرجع `None`.

### 2. اختبارات قراءة وحفظ الإعدادات

ملف مقترح: `tests/test_settings_config.py`

- `test_settings_loads_defaults_when_config_missing`
  - اضبط `config_file` إلى ملف مؤقت غير موجود.
  - استدع `load_config`.
  - تحقق من القيم الافتراضية وحضور كل عناصر التحويل الأربعة.

- `test_settings_save_config_writes_label_geometry_and_printer`
  - أنشئ `SettingsDialog`.
  - اضبط الطابعة، الأبعاد، الفاصل، الإزاحات، والاتجاه.
  - استدع `save_config`.
  - اقرأ JSON المؤقت وتحقق من القيم.

- `test_settings_save_config_writes_logo_settings`
  - فعّل الشعار واضبط `path`, `x`, `y`, `angle`, `logo_settings`.
  - احفظ وتحقق من JSON.

- `test_settings_save_config_writes_all_element_controls`
  - غيّر `show/text/x/y/size/font/angle` لعناصر مثل `store`, `weight`, `date`.
  - احفظ وتحقق من JSON.

- `test_settings_save_config_writes_conversion_elements`
  - فعّل `conv_gold_730`, `conv_gold_750`, `conv_silver_925`, `conv_silver_9999`.
  - غيّر بادئة كل عنصر.
  - احفظ وتحقق أن كل عنصر محفوظ تحت `elements`.

- `test_settings_save_config_writes_equivalent_weight_visibility_by_metal`
  - غيّر `show_for_gold` و `show_for_silver`.
  - احفظ وتحقق من القيم.

- `test_reference_purity_section_is_not_required_for_save`
  - تحقق أن الكائن لا يحتاج `sp_ref_gold` ولا `sp_ref_silver`.
  - استدع `save_config` وتأكد أنه لا يرفع خطأ.

### 3. اختبارات الواجهة الرئيسية والحسابات

ملف مقترح: `tests/test_main_dialog_data_flow.py`

- `test_main_load_config_merges_missing_conversion_defaults`
  - اكتب JSON مؤقتًا قديمًا لا يحتوي عناصر التحويل الجديدة.
  - اضبط `dialog.config_file`.
  - استدع `load_config`.
  - تحقق أن التحويلات الأربعة موجودة بقيمها الافتراضية.

- `test_live_gold_shows_730_primary_and_750_extra`
  - أدخل وزن `4.25` وذهب `750`.
  - استدع `update_live_equiv`.
  - تحقق أن العنوان الأساسي `730` والقيمة `4.37 g`.
  - تحقق أن `750` ظاهر وقيمته `4.25 g`.

- `test_live_silver_shows_925_primary_and_9999_extra`
  - أدخل وزن `3.20` وفضة `925`.
  - تحقق أن العنوان الأساسي `925`.
  - تحقق أن `999.9` ظاهر وقيمته محسوبة بالصيغة.

- `test_live_conversions_are_metal_specific`
  - عند الذهب لا تظهر تحويلات الفضة الحية.
  - عند الفضة لا تظهر تحويلات الذهب الحية.

- `test_comma_decimal_inputs_are_supported`
  - أدخل `3,5` كوزن و `750` كعيار.
  - تحقق أن الحساب لا يفشل ويعرض نتيجة صحيحة.

- `test_print_label_saves_record_with_calculated_equivalent_weight`
  - استخدم JSON مؤقت فيه `printer_name`.
  - monkeypatch لـ `save_print_record` لالتقاط القيم بدل SQLite.
  - monkeypatch للطباعة الفعلية.
  - أدخل ذهب واحفظ.
  - تحقق أن المعدن `Or`، العيار والوزن والوزن المحول صحيحة.

- `test_print_label_uses_only_gold_or_silver_input`
  - إذا أدخل المستخدم ذهبًا، تكون النتيجة ذهب.
  - إذا أدخل فضة فقط، تكون النتيجة فضة.

- `test_label_conversion_elements_respect_show_flags_and_metal`
  - فعّل كل عناصر التحويل في JSON.
  - اطبع ذهبًا.
  - تحقق أن عناصر الذهب فقط تدخل الرسم/النص النهائي.
  - كرر للفضة.

### 4. اختبارات معاينة الملصق في الإعدادات

ملف مقترح: `tests/test_settings_preview.py`

- `test_preview_generates_image_with_expected_size`
  - اضبط العرض والارتفاع.
  - استدع `get_pil_image`.
  - تحقق من أبعاد الصورة بالبكسل.

- `test_preview_respects_disabled_elements`
  - عطل عنصرًا مثل `weight`.
  - monkeypatch لـ `_draw_rotated_text` لتسجيل النصوص بدل الرسم.
  - تحقق أن نص العنصر المعطل غير مرسوم.

- `test_preview_draws_only_gold_conversion_samples`
  - لأن المعاينة الحالية تستخدم عينة `Or`.
  - تحقق أن `conv_gold_730` و `conv_gold_750` يمكن رسمهما.
  - تحقق أن عناصر الفضة لا ترسم في معاينة الذهب.

- `test_preview_respects_equiv_weight_show_for_gold`
  - عطل `chk_equiv_gold`.
  - تحقق أن `equiv_weight` لا يرسم في المعاينة.

### 5. اختبارات نافذة السجل

ملف مقترح: `tests/test_history_dialog.py`

- `test_history_load_data_no_db_does_not_crash`
  - اضبط `DB_FILE` إلى ملف غير موجود.
  - أنشئ النافذة واستدع `load_data`.
  - تحقق أن الجدول فارغ.

- `test_history_load_data_populates_table`
  - أنشئ قاعدة مؤقتة وجدولًا وسجلين.
  - اضبط `ui.history_dialog.DB_FILE`.
  - استدع `load_data`.
  - تحقق من عدد الصفوف وقيم الأعمدة.

- `test_history_date_filter_limits_rows`
  - أدخل سجلات داخل وخارج الفترة.
  - اضبط `date_from` و `date_to`.
  - استدع `load_data`.
  - تحقق أن الجدول يعرض السجلات داخل الفترة فقط.

- `test_history_id_search_returns_single_row`
  - أدخل عدة سجلات.
  - ضع ID في `inp_search_id`.
  - استدع `load_data`.
  - تحقق أن الجدول يحتوي السجل المطلوب فقط.

- `test_history_show_details_uses_row_user_role`
  - حمل البيانات وحدد صفًا.
  - استدع `show_details`.
  - تحقق من كل labels الخاصة بالتفاصيل.

- `test_history_pagination_updates_buttons_and_page_label`
  - أدخل أكثر من `page_size`.
  - تحقق أن `total_pages` أكبر من 1.
  - اختبر `next_page` و `prev_page`.

## اختبارات Regression مهمة

- نافذة الإعدادات لا تحتوي على قسم `العيار المرجعي للتحويل`.
- الحفظ لا يحتاج حقول `sp_ref_gold` و `sp_ref_silver`.
- الذهب يدعم `730` و `750` في الملصق.
- الفضة تدعم `925` و `999.9` في الملصق.
- الثيم الأبيض لا يعتمد على ثيم النظام.
- `label_config.json` القديم الذي لا يحتوي عناصر التحويل الجديدة يتم دمجه مع defaults بدون crash.

## تجهيز بيئة pytest المقترحة

ملف مقترح: `tests/conftest.py`

- fixture `qapp`:
  - ينشئ `QApplication.instance()` أو `QApplication([])`.
- fixture `temp_config_path`:
  - يرجع `tmp_path / "label_config.json"`.
- fixture `temp_db_path`:
  - يرجع `tmp_path / "print_history.db"`.
- fixture `isolated_database`:
  - يعمل monkeypatch لـ `database.DB_FILE`.
  - يعمل monkeypatch لـ `ui.history_dialog.DB_FILE`.
- fixture `no_message_boxes`:
  - يمنع `QMessageBox` من فتح نوافذ حقيقية.
- fixture `no_real_printing`:
  - يمنع `win32print` من الوصول للطابعة.

## معايير القبول

- يمكن تشغيل الاختبارات دون تعديل أو إنشاء `label_config.json` الحقيقي.
- يمكن تشغيل الاختبارات دون تعديل أو إنشاء `print_history.db` الحقيقي.
- كل اختبارات قاعدة البيانات تعمل على SQLite مؤقت.
- كل اختبارات الإعدادات تحفظ إلى JSON مؤقت.
- كل اختبارات العرض تتحقق من النصوص والقيم المرئية لا من مجرد عدم وجود crash.
- التحويلات تتحقق بالأرقام وبحسب المعدن:
  - ذهب `730`
  - ذهب `750`
  - فضة `925`
  - فضة `999.9`
- لا توجد طباعة فعلية أثناء الاختبارات.
