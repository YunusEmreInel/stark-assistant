STATE_TEXT = {
    "initializing": "Hazırlanıyor",
    "idle": "Beklemede",
    "listening": "Dinliyor",
    "capturing": "Dinliyor",
    "transcribing": "Anlıyor",
    "thinking": "Düşünüyor",
    "speaking": "Konuşuyor",
    "paused": "Duraklatıldı",
    "error": "Hata",
    "stopped": "Kapandı",
}

STATE_HINT = {
    "initializing": "Modeller yükleniyor",
    "idle": "Uyandırmak için “Stark” deyin",
    "listening": "Konuşabilirsiniz · 10 sn sessizlikte beklemeye döner",
    "capturing": "Konuşmanızın bitmesi bekleniyor",
    "transcribing": "Konuşma yazıya çevriliyor",
    "thinking": "Yanıt hazırlanıyor",
    "speaking": "Durdurmak için Ctrl+Alt+S",
    "paused": "Mikrofon kapalı",
    "error": "",
    "stopped": "",
}

# Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10) kod noktaları
ICON = {
    "mic": "", "pause": "", "play": "", "stop": "", "new": "",
    "history": "", "settings": "", "power": "", "minimize": "", "info": "",
}

ACCENT = "#E8A23A"

QSS = f"""
* {{ font-family: 'Segoe UI Variable Text', 'Segoe UI'; }}
QWidget {{ background: #0A0A0B; color: #E6E6E8; font-size: 10pt; }}
QToolTip {{ background: #1C1C1F; color: #E6E6E8; border: 1px solid #2E2E32; padding: 4px 6px; }}

/* başlık ve durum çubuğu */
QFrame#header {{ background: #0E0E10; border-bottom: 1px solid #1F1F23; }}
QLabel#brand {{ background: transparent; color: #F2F2F4; font-size: 10pt; font-weight: 600; letter-spacing: 3px; }}
QLabel#chip {{ background: #141417; border: 1px solid #26262B; border-radius: 4px; padding: 3px 8px;
               color: #A8A8B0; font-size: 8.5pt; }}
QFrame#footer {{ background: #0E0E10; border-top: 1px solid #1F1F23; }}
QLabel#footerText {{ background: transparent; color: #6E6E78; font-size: 8.5pt; }}

/* durum */
QLabel#stateTitle {{ background: transparent; color: {ACCENT}; font-size: 9pt; font-weight: 600; letter-spacing: 2px; }}
QLabel#stateHint {{ background: transparent; color: #7A7A84; font-size: 9pt; }}

/* konuşma paneli */
QFrame#panel {{ background: #111113; border: 1px solid #222226; border-radius: 6px; }}
QLabel#panelTitle {{ background: transparent; color: #7A7A84; font-size: 8pt; font-weight: 600; letter-spacing: 1.5px; }}
QTextBrowser#transcript {{ background: transparent; border: none; color: #E6E6E8; font-size: 10.5pt; }}

/* araç çubuğu */
QToolButton {{ background: #141417; border: 1px solid #26262B; border-radius: 6px; color: #C8C8CE;
               font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: 13pt; }}
QToolButton:hover {{ background: #1C1C20; border-color: #3A3A40; color: #FFFFFF; }}
QToolButton:pressed {{ background: #232328; }}
QToolButton:disabled {{ color: #3E3E44; border-color: #1C1C1F; }}
QToolButton:checked {{ border-color: {ACCENT}; color: {ACCENT}; }}
QToolButton#mic {{ background: #1A140B; border: 1px solid {ACCENT}; border-radius: 28px; color: {ACCENT};
                   font-size: 17pt; }}
QToolButton#mic:hover {{ background: #2A1F0F; color: #FFD08A; }}
QToolButton#mic:disabled {{ border-color: #3A3020; color: #5A4A30; background: #0F0D0A; }}
QToolButton#flat {{ background: transparent; border: none; font-size: 10pt; color: #8A8A94; }}
QToolButton#flat:hover {{ color: #FFFFFF; background: #1C1C20; }}

/* hata */
QFrame#errorBar {{ background: #1E1012; border: 1px solid #4A2226; border-radius: 6px; }}
QFrame#errorBar QLabel {{ background: transparent; color: #F2B8B8; font-size: 9pt; }}
QPushButton {{ background: #1A1A1D; border: 1px solid #2E2E33; border-radius: 4px; padding: 5px 12px;
               color: #E6E6E8; font-size: 9pt; }}
QPushButton:hover {{ background: #232327; border-color: #45454C; }}
QPushButton:default {{ border-color: {ACCENT}; }}

/* diyaloglar */
QDialog {{ background: #0E0E10; }}
QGroupBox {{ background: #111113; border: 1px solid #222226; border-radius: 6px; margin-top: 18px;
             padding: 12px 10px 10px 10px; font-size: 8pt; font-weight: 600; color: #7A7A84; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 2px; padding: 0 0 4px 0; letter-spacing: 1.5px; }}
QGroupBox QLabel, QGroupBox QCheckBox {{ background: transparent; font-size: 9.5pt; font-weight: normal; color: #D0D0D6; }}
QLabel#hint {{ background: transparent; color: #6E6E78; font-size: 8.5pt; font-weight: normal; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ background: #17171A; border: 1px solid #2A2A2F; border-radius: 4px;
                                        padding: 4px 8px; min-height: 20px; color: #E6E6E8; }}
QComboBox:hover, QDoubleSpinBox:hover {{ border-color: #3E3E45; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: #17171A; border: 1px solid #2A2A2F; selection-background-color: #2A2216; }}
QProgressBar {{ background: #17171A; border: 1px solid #2A2A2F; border-radius: 3px; max-height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}
QLineEdit {{ background: #17171A; border: 1px solid #2A2A2F; border-radius: 4px; padding: 6px 8px; color: #E6E6E8; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QListWidget {{ background: #111113; border: 1px solid #222226; border-radius: 6px; padding: 4px; outline: none; }}
QListWidget::item {{ padding: 8px 6px; border-bottom: 1px solid #1C1C20; color: #D0D0D6; }}
QListWidget::item:selected {{ background: #1F1A12; color: #FFFFFF; border-left: 2px solid {ACCENT}; }}
QTextBrowser {{ background: #111113; border: 1px solid #222226; border-radius: 6px; padding: 8px; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: #7A7A84; padding: 8px 16px; border-bottom: 2px solid transparent;
                font-weight: 600; }}
QTabBar::tab:selected {{ color: #F2F2F4; border-bottom-color: {ACCENT}; }}
QTabBar::tab:hover {{ color: #D0D0D6; }}
QSplitter::handle {{ background: #0E0E10; width: 6px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2A2A2F; border-radius: 3px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
