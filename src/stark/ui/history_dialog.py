"""Geçmiş ve hafıza: kalıcı sohbetleri görüntüleme/silme, kaydedilmiş bilgileri ekleme/silme."""
import html
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from ..config import APP_DIR
from ..memory.database import KNOWLEDGE, PERSONAL, PREFERENCE
from .style import ACCENT
from .window_style import dark_title_bar


def _when(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    today = datetime.now().date()
    if d.date() == today:
        return f"Bugün {d:%H:%M}"
    return f"{d:%d.%m.%Y %H:%M}"


def _confirm(parent, text: str) -> bool:
    return QMessageBox.question(parent, "Stark", text) == QMessageBox.StandardButton.Yes


class HistoryDialog(QDialog):
    def __init__(self, repo, parent=None, on_memory_changed=lambda: None):
        super().__init__(parent)
        self.repo = repo
        self.on_memory_changed = on_memory_changed
        self.setWindowTitle("Stark — Geçmiş ve hafıza")
        self.resize(820, 600)
        tabs = QTabWidget()
        tabs.addTab(self._build_history(), "Sohbetler")
        tabs.addTab(self._build_memory(), "Hafıza")
        tabs.addTab(self._build_notes(), "Notlar")
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        note = QLabel(f"Tüm veriler yalnızca bu bilgisayarda ({APP_DIR}) tutulur. Silinen veri geri alınamaz.")
        note.setObjectName("hint")
        bottom.addWidget(note, 1)
        bottom.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addLayout(bottom)
        self._reload_conversations()
        self._reload_memories()
        self._reload_notes()
        dark_title_bar(self)

    # ---- sohbetler ----
    def _build_history(self) -> QWidget:
        self.conv_list = QListWidget()
        self.conv_list.currentItemChanged.connect(self._show_conversation)
        self.conv_view = QTextBrowser()
        del_btn = QPushButton("Sohbeti sil")
        del_all = QPushButton("Tüm geçmişi sil")
        del_btn.clicked.connect(self._delete_conversation)
        del_all.clicked.connect(self._delete_all_conversations)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self.conv_list)
        row = QHBoxLayout()
        row.addWidget(del_btn)
        row.addWidget(del_all)
        lv.addLayout(row)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(self.conv_view)
        split.setSizes([280, 540])
        w = QWidget()
        QVBoxLayout(w).addWidget(split)
        return w

    def _reload_conversations(self) -> None:
        self.conv_list.clear()
        for cid, started, title, count in self.repo.list_conversations():
            item = QListWidgetItem(f"{title or '(başlıksız)'}\n{_when(started)} · {count // 2} tur")
            item.setData(Qt.ItemDataRole.UserRole, cid)
            self.conv_list.addItem(item)
        if self.conv_list.count():
            self.conv_list.setCurrentRow(0)
        else:
            self.conv_view.setHtml("<p style='color:#5A5A62'>Kayıtlı sohbet yok.</p>")

    def _show_conversation(self, item) -> None:
        if item is None:
            self.conv_view.clear()
            return
        rows = []
        for role, content, at in self.repo.messages(item.data(Qt.ItemDataRole.UserRole)):
            name, color, body = ("SİZ", "#8A8A94", "#B8B8C0") if role == "user" else ("STARK", ACCENT, "#ECECEE")
            rows.append(f"<div style='margin-bottom:12px'><span style='color:{color};font-size:8pt;"
                        f"font-weight:600'>{name}</span>&nbsp;&nbsp;<span style='color:#4E4E56;font-size:8pt'>"
                        f"{_when(at)}</span><br><span style='color:{body}'>"
                        f"{html.escape(content).replace(chr(10), '<br>')}</span></div>")
        self.conv_view.setHtml("".join(rows))

    def _delete_conversation(self) -> None:
        item = self.conv_list.currentItem()
        if item and _confirm(self, "Bu sohbet kalıcı olarak silinsin mi?"):
            self.repo.delete_conversation(item.data(Qt.ItemDataRole.UserRole))
            self._reload_conversations()

    def _delete_all_conversations(self) -> None:
        if self.conv_list.count() and _confirm(self, "Tüm sohbet geçmişi kalıcı olarak silinsin mi? "
                                                     "(Hafızadaki bilgiler silinmez. Silinenler en fazla 7 gün "
                                                     "günlük yedeklerde kalır; Ayarlar'dan yedekleri silebilirsiniz.)"):
            self.repo.delete_all_conversations()
            self._reload_conversations()

    # ---- notlar ----
    def _build_notes(self) -> QWidget:
        info = QLabel("Sesle: “Not al: …”, “Notlarımı oku”, “Son notu sil”, “Notlarımı masaüstüne aktar”. "
                      "Notlar hafızadan ayrıdır; Stark onları sohbette kullanmaz.")
        info.setObjectName("hint")
        info.setWordWrap(True)
        self.note_list = QListWidget()
        self.note_input = QLineEdit(placeholderText="Yeni not, ör. Cuma günü kütüphaneye kitap iade et")
        self.note_input.returnPressed.connect(self._add_note)
        add = QPushButton("Not ekle")
        add.clicked.connect(self._add_note)
        delete = QPushButton("Seçileni sil")
        delete.clicked.connect(self._delete_note)
        export = QPushButton("Masaüstüne aktar")
        export.clicked.connect(self._export_notes)
        add_row = QHBoxLayout()
        add_row.addWidget(self.note_input, 1)
        add_row.addWidget(add)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(export)
        btn_row.addWidget(delete)
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(info)
        v.addLayout(add_row)
        v.addWidget(self.note_list)
        v.addLayout(btn_row)
        return w

    def _reload_notes(self) -> None:
        self.note_list.clear()
        for nid, content, created in reversed(self.repo.list_notes()):
            item = QListWidgetItem(f"{content}\n{_when(created)}")
            item.setData(Qt.ItemDataRole.UserRole, nid)
            self.note_list.addItem(item)

    def _add_note(self) -> None:
        text = self.note_input.text().strip()
        if text:
            self.repo.add_note(text)
            self.note_input.clear()
            self._reload_notes()

    def _delete_note(self) -> None:
        item = self.note_list.currentItem()
        if item and _confirm(self, "Bu not silinsin mi?"):
            self.repo.delete_note(item.data(Qt.ItemDataRole.UserRole))
            self._reload_notes()

    def _export_notes(self) -> None:
        notes = self.repo.list_notes()
        if not notes:
            return
        from ..tools.desktop import create_on_desktop
        body = "\n".join(f"- {c}  ({created[:10]})" for _, c, created in notes)
        path = create_on_desktop("Stark notları", "dosya", body)
        QMessageBox.information(self, "Stark", f"Notlar masaüstüne kaydedildi:\n{path.name}")

    # ---- hafıza ----
    def _build_memory(self) -> QWidget:
        info = QLabel("Stark yalnızca burada kayıtlı bilgileri hatırlar. Sesle: kendinizle ilgili bilgi için "
                      "“Bunu hatırla: …”, genel bilgi öğretmek için “Şunu öğren: …”, silmek için “Unut: …”. "
                      "Bu bir model eğitimi değildir; kayıtlar ilgili sorularda Stark'a hatırlatılır.")
        info.setObjectName("hint")
        info.setWordWrap(True)
        self.mem_list = QListWidget()
        self.mem_input = QLineEdit(placeholderText="ör. En sevdiğim renk mavi  /  Bornova, İzmir'in bir ilçesidir")
        self.mem_input.returnPressed.connect(lambda: self._add_memory(PERSONAL))
        add = QPushButton("Kişisel bilgi ekle")
        add.clicked.connect(lambda: self._add_memory(PERSONAL))
        teach = QPushButton("Genel bilgi öğret")
        teach.clicked.connect(lambda: self._add_memory(KNOWLEDGE))
        delete = QPushButton("Seçileni sil")
        delete.clicked.connect(self._delete_memory)
        delete_all = QPushButton("Tüm hafızayı sil")
        delete_all.clicked.connect(self._delete_all_memories)
        add_row = QHBoxLayout()
        add_row.addWidget(self.mem_input, 1)
        add_row.addWidget(add)
        add_row.addWidget(teach)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(delete)
        btn_row.addWidget(delete_all)
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(info)
        v.addLayout(add_row)
        v.addWidget(self.mem_list)
        v.addLayout(btn_row)
        return w

    def _reload_memories(self) -> None:
        self.mem_list.clear()
        kinds, sources = self.repo.kinds(), self.repo.sources()
        for mid, content, created in reversed(self.repo.list_memories()):
            kind = {KNOWLEDGE: "Bilgi", PREFERENCE: "Tercih"}.get(kinds.get(mid), "Kişisel")
            origin = {"auto": "konuşmadan kendisi öğrendi", "web": "internetten öğrendi (süreli)"}.get(
                sources.get(mid), "sizin öğrettiğiniz")
            label = f"{kind} · {origin}"
            item = QListWidgetItem(f"{content}\n{label} · {_when(created)}")
            item.setData(Qt.ItemDataRole.UserRole, mid)
            self.mem_list.addItem(item)

    def _add_memory(self, kind: str = PERSONAL) -> None:
        text = self.mem_input.text().strip()
        if text:
            self.repo.add_memory(text, kind)
            self.mem_input.clear()
            self._reload_memories()
            self.on_memory_changed()

    def _delete_memory(self) -> None:
        item = self.mem_list.currentItem()
        if item:
            self.repo.delete_memory(item.data(Qt.ItemDataRole.UserRole))
            self._reload_memories()
            self.on_memory_changed()

    def _delete_all_memories(self) -> None:
        if self.mem_list.count() and _confirm(self, "Hafızadaki tüm bilgiler kalıcı olarak silinsin mi? (Silinenler "
                                                    "en fazla 7 gün günlük yedeklerde kalır; Ayarlar'dan yedekleri "
                                                    "silebilirsiniz.)"):
            self.repo.delete_all_memories()
            self._reload_memories()
            self.on_memory_changed()
