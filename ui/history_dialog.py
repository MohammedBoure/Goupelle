# ui/history_dialog.py
import sqlite3
import os
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLabel, QDateEdit, QSplitter, QWidget, QMessageBox, 
    QAbstractItemView, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QDate

DB_FILE = "print_history.db"

class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("سجل الطباعة وقاعدة البيانات")
        
        # 1. فرض اتجاه الواجهة من اليمين إلى اليسار (أساسي للتطبيقات العربية)
        self.setLayoutDirection(Qt.RightToLeft)
        
        # 2. إعدادات النافذة والتكبير
        self.setMinimumSize(1100, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        
        self.page_size = 100
        self.current_page = 1
        self.total_pages = 1
        
        self.init_ui()
        self.apply_styles()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # ==========================================
        # 1. شريط الفلاتر والبحث (تم إصلاح التمدد)
        # ==========================================
        filter_frame = QFrame()
        filter_frame.setObjectName("filter_frame")
        
        # الحل السحري لمنع الشريط العلوي من التمدد عمودياً
        filter_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(15, 15, 15, 15)
        filter_layout.setSpacing(15)
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setFixedWidth(140)
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setFixedWidth(140)
        
        self.inp_search_id = QLineEdit()
        self.inp_search_id.setPlaceholderText("رقم الـ ID...")
        self.inp_search_id.setFixedWidth(150)
        
        btn_search = QPushButton("بحث 🔎")
        btn_search.setObjectName("btn_search")
        btn_search.clicked.connect(self.on_search_clicked)
        btn_search.setCursor(Qt.PointingHandCursor)
        
        btn_reset = QPushButton("إعادة ضبط 🔄")
        btn_reset.setObjectName("btn_reset")
        btn_reset.clicked.connect(self.reset_filters)
        btn_reset.setCursor(Qt.PointingHandCursor)
        
        # ترتيب العناصر في الشريط
        filter_layout.addWidget(QLabel("من تاريخ:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("إلى تاريخ:"))
        filter_layout.addWidget(self.date_to)
        
        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet("color: #bdc3c7;")
        filter_layout.addWidget(vline)
        
        filter_layout.addWidget(QLabel("أو بحث دقيق:"))
        filter_layout.addWidget(self.inp_search_id)
        filter_layout.addWidget(btn_search)
        filter_layout.addWidget(btn_reset)
        filter_layout.addStretch() # لدفع العناصر نحو اليمين
        
        main_layout.addWidget(filter_frame)

        # ==========================================
        # 2. منطقة العرض (المقسّم - Splitter)
        # ==========================================
        self.splitter = QSplitter(Qt.Horizontal)
        
        # --- اللوحة اليمنى (كانت يسرى قبل الـ RTL): الجدول ---
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(10)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "التاريخ والوقت", "المعدن", "العيار", "الوزن الفعلي"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.show_details)
        
        table_layout.addWidget(self.table)
        
        # --- أدوات تقليب الصفحات ---
        pagination_frame = QFrame()
        pagination_layout = QHBoxLayout(pagination_frame)
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_prev = QPushButton("◀ السابقة") # تم عكس الأسهم لتناسب RTL
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        
        self.lbl_page_info = QLabel("صفحة 1 من 1")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #34495e;")
        
        self.btn_next = QPushButton("التالية ▶")
        self.btn_next.clicked.connect(self.next_page)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.btn_next)
        pagination_layout.addWidget(self.lbl_page_info)
        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addStretch()
        
        table_layout.addWidget(pagination_frame)
        self.splitter.addWidget(table_container)

        # --- اللوحة اليسرى: العرض التفصيلي ---
        details_frame = QFrame()
        details_frame.setObjectName("details_frame")
        self.details_layout = QVBoxLayout(details_frame)
        self.details_layout.setAlignment(Qt.AlignTop)
        self.details_layout.setSpacing(20)
        
        det_title = QLabel("📋 تفاصيل الطلب المحدد")
        det_title.setObjectName("det_title")
        det_title.setAlignment(Qt.AlignCenter)
        self.details_layout.addWidget(det_title)
        
        hline = QFrame()
        hline.setFrameShape(QFrame.HLine)
        hline.setStyleSheet("color: #ecf0f1;")
        self.details_layout.addWidget(hline)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.lbl_det_id = QLabel("-")
        self.lbl_det_date = QLabel("-")
        self.lbl_det_metal = QLabel("-")
        self.lbl_det_purity = QLabel("-")
        self.lbl_det_weight = QLabel("-")
        self.lbl_det_equiv = QLabel("-")
        self.lbl_det_printer = QLabel("-")
        
        for lbl in [self.lbl_det_id, self.lbl_det_date, self.lbl_det_metal, 
                    self.lbl_det_purity, self.lbl_det_weight, self.lbl_det_printer]:
            lbl.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 15px;")

        self.lbl_det_equiv.setObjectName("lbl_equiv")

        form_layout.addRow(QLabel("رقم الطلب (ID):"), self.lbl_det_id)
        form_layout.addRow(QLabel("تاريخ الطباعة:"), self.lbl_det_date)
        form_layout.addRow(QLabel("نوع المعدن:"), self.lbl_det_metal)
        form_layout.addRow(QLabel("العيار الفعلي:"), self.lbl_det_purity)
        form_layout.addRow(QLabel("الوزن الفعلي:"), self.lbl_det_weight)
        form_layout.addRow(QLabel("طُبع بواسطة:"), self.lbl_det_printer)
        form_layout.addRow(QLabel(""), QLabel("")) 
        form_layout.addRow(QLabel("الوزن المحول (Eq):"), self.lbl_det_equiv)
        
        self.details_layout.addLayout(form_layout)
        self.details_layout.addStretch()
        
        self.splitter.addWidget(details_frame)
        self.splitter.setSizes([800, 300]) 
        
        main_layout.addWidget(self.splitter)

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                font-family: "Segoe UI", "Arial";
            }
            QFrame#filter_frame {
                background-color: #ffffff;
                border: 1px solid #dcdde1;
                border-radius: 8px;
            }
            QFrame#details_frame {
                background-color: #ffffff;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel#det_title {
                font-size: 18px;
                font-weight: bold;
                color: #2980b9;
                padding-bottom: 5px;
            }
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                font-weight: bold;
            }
            QLabel#lbl_equiv {
                font-size: 18px;
                font-weight: bold;
                color: #27ae60;
                background-color: #eafaf1;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QLineEdit, QDateEdit {
                padding: 6px 10px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 14px;
                background-color: #ffffff;
                min-height: 25px;
            }
            QLineEdit:focus, QDateEdit:focus {
                border: 2px solid #3498db;
                background-color: #ffffff;
            }
            QPushButton#btn_search {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton#btn_search:hover {
                background-color: #3498db;
            }
            QPushButton#btn_reset {
                background-color: #ffffff;
                color: #2c3e50;
                font-weight: bold;
                border-radius: 5px;
                border: 1px solid #bdc3c7;
                padding: 8px 15px;
                font-size: 14px;
            }
            QPushButton#btn_reset:hover {
                background-color: #f8fafc;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #ffffff;
                border: 1px solid #dcdde1;
                border-radius: 5px;
                font-size: 14px;
                selection-background-color: #3498db;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #ffffff;
                color: #2c3e50;
                padding: 10px;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-left: 1px solid #dcdde1;
                border-bottom: 2px solid #bdc3c7;
            }
            QPushButton {
                padding: 6px 15px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
            QPushButton:disabled {
                background-color: #f9f9f9;
                color: #bdc3c7;
                border: 1px solid #ecf0f1;
            }
        """)

    def reset_filters(self):
        self.inp_search_id.clear()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())
        self.current_page = 1
        self.load_data()

    def on_search_clicked(self):
        self.current_page = 1
        self.load_data()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()

    def load_data(self):
        if not os.path.exists(DB_FILE):
            return

        search_id = self.inp_search_id.text().strip()
        start_str = self.date_from.date().toString("yyyy-MM-dd 00:00:00")
        end_str = self.date_to.date().toString("yyyy-MM-dd 23:59:59")
        
        query_conditions = "1=1"
        params = []
        
        if search_id:
            query_conditions += " AND id = ?"
            params.append(search_id)
        else:
            query_conditions += " AND print_time >= ? AND print_time <= ?"
            params.extend([start_str, end_str])

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                
                cursor.execute(f"SELECT COUNT(*) FROM printed_labels WHERE {query_conditions}", params)
                total_records = cursor.fetchone()[0]
                
                self.total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)
                
                self.lbl_page_info.setText(f"صفحة {self.current_page} من {self.total_pages} (إجمالي: {total_records})")
                self.btn_prev.setEnabled(self.current_page > 1)
                self.btn_next.setEnabled(self.current_page < self.total_pages)

                offset = (self.current_page - 1) * self.page_size
                data_query = f"""
                    SELECT id, print_time, metal_type, actual_purity, actual_weight, equivalent_weight, printer_name 
                    FROM printed_labels 
                    WHERE {query_conditions} 
                    ORDER BY print_time DESC 
                    LIMIT ? OFFSET ?
                """
                cursor.execute(data_query, params + [self.page_size, offset])
                records = cursor.fetchall()

                self.table.setRowCount(0)
                for row_idx, row_data in enumerate(records):
                    self.table.insertRow(row_idx)
                    
                    self.table.setItem(row_idx, 0, QTableWidgetItem(str(row_data[0])))
                    self.table.setItem(row_idx, 1, QTableWidgetItem(str(row_data[1])))
                    self.table.setItem(row_idx, 2, QTableWidgetItem(str(row_data[2])))
                    self.table.setItem(row_idx, 3, QTableWidgetItem(f"{row_data[3]:g}"))
                    self.table.setItem(row_idx, 4, QTableWidgetItem(f"{row_data[4]:g} g"))
                    
                    item_id = self.table.item(row_idx, 0)
                    item_id.setData(Qt.UserRole, row_data)
                    
                    for col in range(5):
                        self.table.item(row_idx, col).setTextAlignment(Qt.AlignCenter)

                self.clear_details()

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء جلب البيانات:\n{str(e)}")

    def show_details(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            self.clear_details()
            return
        
        row_data = self.table.item(selected_items[0].row(), 0).data(Qt.UserRole)
        if not row_data: return

        self.lbl_det_id.setText(str(row_data[0]))
        self.lbl_det_date.setText(str(row_data[1]))
        self.lbl_det_metal.setText(str(row_data[2]))
        self.lbl_det_purity.setText(f"{row_data[3]:g}")
        self.lbl_det_weight.setText(f"{row_data[4]:g} g")
        self.lbl_det_equiv.setText(f"{row_data[5]:.2f} g")
        self.lbl_det_printer.setText(str(row_data[6]))

    def clear_details(self):
        self.lbl_det_id.setText("-")
        self.lbl_det_date.setText("-")
        self.lbl_det_metal.setText("-")
        self.lbl_det_purity.setText("-")
        self.lbl_det_weight.setText("-")
        self.lbl_det_equiv.setText("-")
        self.lbl_det_printer.setText("-")
