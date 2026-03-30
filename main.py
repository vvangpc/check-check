import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QTextEdit, QLabel, QSplitter, 
                             QMessageBox, QListWidget, QListWidgetItem, QMenu, QDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QBrush, QTextCursor, QAction

# 加载业务模块
from src.document_parser import parse_file, split_patent_document
from src.rules_checker import checker

class RequireDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 - 文本要求")
        self.resize(500, 300)
        layout = QVBoxLayout(self)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setText("上传文本要求与智能分割提示：\n\n1. 权利要求书的开头需满足以下任一定式：\n【1.一种XXX】或【1、一种XXX】（并随后带有“其特征”等字样）\n\n2. 说明书须带有以下字样作为分割点识别起点：\n【一种XXXXX 技术领域】\n\n3. 说明书结尾必须以以下规定的一句话作为结尾：\n在上述发明的基础上还可以做出其它变化或变型，并且这些变化或变型仍处于本发明的范围内。")
        layout.addWidget(te)
        
        btn = QPushButton("确定")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Check-Check")
        self.resize(1200, 800)
        self.initUI()

        self.claims_text = ""
        self.specs_text = ""

    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 头部：按钮栏
        header_layout = QHBoxLayout()
        self.btn_upload = QPushButton("上传文件及自动分割")
        self.btn_upload.clicked.connect(self.upload_file)
        self.btn_check = QPushButton("开始形式审查")
        self.btn_check.clicked.connect(self.run_checks)
        self.btn_check.setEnabled(False)
        self.btn_settings = QPushButton("设置")
        
        # 设置下拉菜单
        settings_menu = QMenu(self)
        action_req = QAction("文本要求", self)
        action_req.triggered.connect(self.show_text_requirements)
        settings_menu.addAction(action_req)
        self.btn_settings.setMenu(settings_menu)

        header_layout.addWidget(self.btn_upload)
        header_layout.addWidget(self.btn_check)
        header_layout.addWidget(self.btn_settings)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # 中部：带分割器的整体三面布局 (纵向)
        self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 纵向的上部分：带横向分割的文档对比区
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 权利要求面板
        panel_claims = QWidget()
        layout_claims = QVBoxLayout(panel_claims)
        layout_claims.addWidget(QLabel("📝 权利要求书 (Claims)"))
        self.txt_claims = QTextEdit()
        layout_claims.addWidget(self.txt_claims)
        
        # 说明书面板
        panel_specs = QWidget()
        layout_specs = QVBoxLayout(panel_specs)
        layout_specs.addWidget(QLabel("📖 说明书 (Specification)"))
        self.txt_specs = QTextEdit()
        layout_specs.addWidget(self.txt_specs)

        self.h_splitter.addWidget(panel_claims)
        self.h_splitter.addWidget(panel_specs)
        
        self.main_v_splitter.addWidget(self.h_splitter)

        # 纵向的下部分：报告展区 (支持 QListWidgetItem 双击)
        panel_report = QWidget()
        layout_report = QVBoxLayout(panel_report)
        layout_report.addWidget(QLabel("⚡ 智能审查报告 (双击列表项可直接跳转至错误位置，并支持选中复制/高亮标注)："))
        self.list_report = QListWidget()
        self.list_report.setStyleSheet("""
            QListWidget { background-color: #2b2b2b; color: #a9b7c6; font-family: Consolas, monospace; font-size: 14px; }
            QListWidget::item { padding: 5px; }
            QListWidget::item:selected { background-color: #4b6eaf; color: white; }
        """)
        self.list_report.itemDoubleClicked.connect(self.on_report_double_clicked)
        layout_report.addWidget(self.list_report)
        
        self.main_v_splitter.addWidget(panel_report)
        main_layout.addWidget(self.main_v_splitter)

    def show_text_requirements(self):
        diag = RequireDialog(self)
        diag.exec()

    def upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择专利申请文件",
            "",
            "支持的文件 (*.docx *.rtf *.txt)"
        )
        if not file_path:
            return

        try:
            self.list_report.clear()
            self.list_report.addItem(f"> 成功读取文件: {file_path}")
            raw_text = parse_file(file_path)
            
            # 自动分割逻辑
            parts = split_patent_document(raw_text)
            self.claims_text = parts.get("claims", "")
            self.specs_text = parts.get("specification", "")

            # 填充 UI
            self.txt_claims.setPlainText(self.claims_text)
            self.txt_specs.setPlainText(self.specs_text)
            
            # 启用审查按钮
            self.btn_check.setEnabled(True)
            self.list_report.addItem("> 文档分割完成！如果不准请手动截断复制修正，确认无误后请点击「开始形式审查」。")

        except Exception as e:
            self.list_report.addItem(f"❌ 读取错误: {str(e)}")

    def run_checks(self):
        # 清空原有的所有高亮底色
        self.clear_highlight(self.txt_claims)
        self.clear_highlight(self.txt_specs)

        # 允许用户在UI中修改后再次检验，所以从TextEdit读取最新文本
        self.claims_text = self.txt_claims.toPlainText()
        self.specs_text = self.txt_specs.toPlainText()

        self.list_report.clear()
        self.list_report.addItem("正在执行形式审查与逻辑分析...")
        
        report_strings, issues = checker.analyze_patent(self.claims_text, self.specs_text)
        
        for issue in issues:
            item = QListWidgetItem(issue["text"])
            # 保存元数据到列表项中以供双击使用
            item.setData(Qt.ItemDataRole.UserRole, issue)
            self.list_report.addItem(item)
            
            # 根据错误级别为原文本上底色
            if issue["type"] == "claims_error":     # 确定错误 (敏感词、残破字) -> 红色底
                self.apply_highlight(self.txt_claims, issue["span"], QColor("#FF6B6B"))
            elif issue["type"] == "claims_warning": # 可以错误 (缺乏说明支持) -> 黄色底
                self.apply_highlight(self.txt_claims, issue["span"], QColor("#FFD93D"))

        if not issues:
            self.list_report.addItem("恭喜！未在本文档中检测到明显的形缺问题。")

    def clear_highlight(self, text_edit):
        """清空富文本框里的底色光标高亮"""
        cursor = text_edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(Qt.GlobalColor.transparent)) # 把背景重置为透明
        cursor.setCharFormat(fmt)
        cursor.clearSelection()
        text_edit.setTextCursor(cursor)
        
    def apply_highlight(self, text_edit, span, color):
        """为指定的 Start-End 区间打上背景色高亮"""
        cursor = text_edit.textCursor()
        cursor.setPosition(span[0])
        cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setBackground(color)
        fmt.setForeground(QColor("black")) # 防止深色底色下看不清
        cursor.setCharFormat(fmt)

    def on_report_double_clicked(self, item):
        """双击报告项目自动跳转到文档文本框的特定错误词位置"""
        issue = item.data(Qt.ItemDataRole.UserRole)
        if not issue: 
            return # 第一行日志和最后一行并不是issue
            
        span = issue["span"]
        if "claims" in issue["type"]:
            cursor = self.txt_claims.textCursor()
            cursor.setPosition(span[0])
            cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
            self.txt_claims.setTextCursor(cursor)
            self.txt_claims.setFocus()            # 将焦点设定至权利要求多行输入框
            self.txt_claims.ensureCursorVisible() # 自动滚动到该词所在视口区域

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
