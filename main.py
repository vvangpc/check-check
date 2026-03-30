import sys
import re
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QTextEdit, QLabel, QSplitter, 
                             QMessageBox, QListWidget, QListWidgetItem, QMenu, QDialog,
                             QColorDialog, QStatusBar, QProgressBar, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression, QEvent
from PyQt6.QtGui import QTextCharFormat, QColor, QBrush, QTextCursor, QAction, QSyntaxHighlighter, QPalette

# 加载业务模块
from src.document_parser import parse_file, split_patent_document
from src.rules_checker import checker
from src.config import config

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

class ThemeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 - 主题颜色")
        self.resize(300, 200)
        self.main_window = parent
        
        layout = QVBoxLayout(self)
        
        btn_claims = QPushButton("选择权利要求框背景颜色")
        btn_specs = QPushButton("选择说明书框背景颜色")
        btn_report = QPushButton("选择智能审查报告背景颜色")
        
        btn_claims.clicked.connect(lambda: self.choose_color("claims"))
        btn_specs.clicked.connect(lambda: self.choose_color("specs"))
        btn_report.clicked.connect(lambda: self.choose_color("report"))
        
        layout.addWidget(btn_claims)
        layout.addWidget(btn_specs)
        layout.addWidget(btn_report)
        
        btn = QPushButton("关闭")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        
    def choose_color(self, target):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            if target == "claims":
                self.main_window.set_widget_theme(self.main_window.txt_claims, color)
                self.main_window.current_theme["claims"] = hex_color
            elif target == "specs":
                self.main_window.set_widget_theme(self.main_window.txt_specs, color)
                self.main_window.current_theme["specs"] = hex_color
            elif target == "report":
                self.main_window.set_widget_theme(self.main_window.list_report, color)
                self.main_window.current_theme["report"] = hex_color
                
            try:
                with open(self.main_window.settings_file, "w", encoding="utf-8") as f:
                    json.dump(self.main_window.current_theme, f, ensure_ascii=False, indent=4)
            except Exception:
                pass

class PatentHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = [] 
        
    def set_rules(self, regexes, background_color):
        """传递一系列重编译的正则列表进实时高亮器"""
        self.highlightingRules.clear()
        
        format = QTextCharFormat()
        format.setBackground(background_color)
        text_color = QColor("black") if background_color.lightness() > 128 else QColor("white")
        format.setForeground(text_color)
        
        for qregex in regexes:
            self.highlightingRules.append((qregex, format))
        
        self.rehighlight()

    def highlightBlock(self, text):
        for regex, format in self.highlightingRules:
            iterator = regex.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                if match.capturedLength() > 0:
                    self.setFormat(match.capturedStart(), match.capturedLength(), format)

class WorkerThread(QThread):
    finished = pyqtSignal(list, list) # report, issues
    error = pyqtSignal(str)
    
    def __init__(self, claims_text, specs_text):
        super().__init__()
        self.claims_text = claims_text
        self.specs_text = specs_text
        
    def run(self):
        try:
            report, issues = checker.analyze_patent(self.claims_text, self.specs_text)
            self.finished.emit(report, issues)
        except Exception as e:
            import traceback
            self.error.emit(f"审查过程发生致命崩溃: {str(e)}\n\n报错详情：\n{traceback.format_exc()}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Check-Check")
        self.resize(1200, 800)
        self.claims_text = ""
        self.specs_text = ""
        self.worker = None
        self.last_focused_box = None
        
        self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        self.current_theme = {
            "claims": "#ffffff",
            "specs": "#ffffff",
            "report": "#ffffff"
        }
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.current_theme.update(saved)
            except Exception:
                pass

        self.initUI()
        self.init_highlighters()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn:
            if obj is self.txt_claims or obj is self.txt_specs:
                self.last_focused_box = obj
        return super().eventFilter(obj, event)

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
        
        # 搜索功能UI
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("在文档中搜索...")
        self.search_input.setFixedWidth(200)
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.on_search)
        self.search_input.returnPressed.connect(self.on_search)
        
        # 设置下拉菜单
        settings_menu = QMenu(self)
        action_req = QAction("文本要求", self)
        action_req.triggered.connect(self.show_text_requirements)
        
        action_theme = QAction("主题颜色", self)
        action_theme.triggered.connect(self.show_theme_settings)
        
        settings_menu.addAction(action_req)
        settings_menu.addAction(action_theme)
        self.btn_settings.setMenu(settings_menu)

        header_layout.addWidget(self.btn_upload)
        header_layout.addWidget(self.btn_check)
        header_layout.addWidget(self.btn_settings)
        header_layout.addStretch()
        header_layout.addWidget(self.search_input)
        header_layout.addWidget(self.btn_search)

        main_layout.addLayout(header_layout)

        # 中部：带分割器的整体三面布局 (纵向)
        self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 增加 QSplitter 渲染样式：明显的调节线
        splitter_style = """
        QSplitter::handle {
            background-color: #6a6a6a;
            border: 1px solid #444;
            margin: 2px;
        }
        """
        self.main_v_splitter.setStyleSheet(splitter_style)
        
        # 纵向的上部分：带横向分割的文档对比区
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.h_splitter.setStyleSheet(splitter_style)
        
        # 权利要求面板
        panel_claims = QWidget()
        layout_claims = QVBoxLayout(panel_claims)
        layout_claims.addWidget(QLabel("📝 权利要求书 (Claims)"))
        self.txt_claims = QTextEdit()
        self.txt_claims.installEventFilter(self)
        layout_claims.addWidget(self.txt_claims)
        
        # 说明书面板
        panel_specs = QWidget()
        layout_specs = QVBoxLayout(panel_specs)
        layout_specs.addWidget(QLabel("📖 说明书 (Specification)"))
        self.txt_specs = QTextEdit()
        self.txt_specs.installEventFilter(self)
        layout_specs.addWidget(self.txt_specs)

        self.h_splitter.addWidget(panel_claims)
        self.h_splitter.addWidget(panel_specs)
        
        self.main_v_splitter.addWidget(self.h_splitter)

        # 纵向的下部分：报告展区
        panel_report = QWidget()
        layout_report = QVBoxLayout(panel_report)
        layout_report.addWidget(QLabel("⚡ 智能审查报告 (双击列表项可直接跳转至错误位置):"))
        self.list_report = QListWidget()
        layout_report.addWidget(self.list_report)
        
        self.main_v_splitter.addWidget(panel_report)
        main_layout.addWidget(self.main_v_splitter)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.lbl_status = QLabel("就绪")
        self.lbl_stats = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0) # Indeterminate mode for loading animation
        
        self.status_bar.addWidget(self.lbl_status)
        self.status_bar.addWidget(self.progress_bar)
        self.status_bar.addPermanentWidget(self.lbl_stats)

        # 初始主题设置
        self.set_widget_theme(self.txt_claims, QColor(self.current_theme["claims"]))
        self.set_widget_theme(self.txt_specs, QColor(self.current_theme["specs"]))
        self.set_widget_theme(self.list_report, QColor(self.current_theme["report"]))
        
        # 绑定点击事件
        self.list_report.itemDoubleClicked.connect(self.on_report_double_clicked)

    def init_highlighters(self):
        self.highlighter_claims = PatentHighlighter(self.txt_claims.document())
        self.highlighter_specs = PatentHighlighter(self.txt_specs.document())
        
        # 将配置中静态可预测的问题词汇预先加载进实时高亮器 (比如敏感词)
        if config.minganci_regex:
            qregex = QRegularExpression(config.minganci_regex.pattern)
            self.highlighter_claims.set_rules([qregex], QColor("#FF6B6B"))

    def set_widget_theme(self, widget, color):
        font_color = "#000000" if color.lightness() > 128 else "#ffffff"
        bg_rgb = f"rgb({color.red()}, {color.green()}, {color.blue()})"
        
        style = f"background-color: {bg_rgb}; color: {font_color};"
        if isinstance(widget, QListWidget):
            style += "font-family: Consolas, monospace; font-size: 14px;"
            widget.setStyleSheet(f"""
                QListWidget {{ {style} }}
                QListWidget::item {{ padding: 5px; }}
                QListWidget::item:selected {{ background-color: #4b6eaf; color: white; }}
            """)
        else:
            style += "font-family: Consolas, monospace; font-size: 14px;"
            widget.setStyleSheet(f"QTextEdit {{ {style} }}")

    def show_text_requirements(self):
        diag = RequireDialog(self)
        diag.exec()
        
    def show_theme_settings(self):
        diag = ThemeDialog(self)
        diag.exec()

    def on_search(self):
        query = self.search_input.text()
        if not query:
            return
            
        # 根据最近记忆的焦点判断目标文本框，默认使用说明书
        target_box = self.last_focused_box if self.last_focused_box else self.txt_specs
        
        # 执行查找
        found = target_box.find(query)
        if not found:
            # 循环匹配：如果到底了，重置光标从头开始找
            cursor = target_box.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            target_box.setTextCursor(cursor)
            found = target_box.find(query)
            if not found:
                box_name = "权利要求书" if target_box is self.txt_claims else "说明书"
                QMessageBox.information(self, "搜索", f"在 {box_name} 中未找到: '{query}'")

    def update_stats(self):
        c_len = len(self.txt_claims.toPlainText())
        s_len = len(self.txt_specs.toPlainText())
        
        c_items = len(re.findall(r'^(\d+)[\.、]', self.txt_claims.toPlainText(), re.MULTILINE))
        self.lbl_stats.setText(f"字数统计: 权利要求及说明书共 {c_len + s_len} 字 | 权利要求项数: {c_items} 项起")

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
            self.update_stats()

        except Exception as e:
            self.list_report.addItem(f"❌ 读取错误: {str(e)}")

    def run_checks(self):
        self.claims_text = self.txt_claims.toPlainText()
        self.specs_text = self.txt_specs.toPlainText()

        self.list_report.clear()
        self.list_report.addItem("正在进行深度逻辑及形式分析，请稍候...")
        
        self.btn_check.setEnabled(False)
        self.lbl_status.setText("正在分析以生成智能审查报告...")
        self.progress_bar.setVisible(True)
        self.update_stats()
        
        # 启动多线程进行检查
        self.worker = WorkerThread(self.claims_text, self.specs_text)
        self.worker.finished.connect(self.on_check_finished)
        self.worker.error.connect(self.on_check_error)
        self.worker.start()

    def on_check_error(self, err_msg):
        self.btn_check.setEnabled(True)
        self.lbl_status.setText("分析中止，遭遇严重异常")
        self.progress_bar.setVisible(False)
        self.list_report.clear()
        
        item = QListWidgetItem(err_msg)
        self.list_report.addItem(item)
        
        QMessageBox.critical(self, "解析引擎崩溃", "专利检查过程因为不规则文字引发了解析崩溃，详情请查看报告窗口底侧输出！")

    def on_check_finished(self, report_strings, issues):
        self.btn_check.setEnabled(True)
        self.lbl_status.setText("分析完成，就绪")
        self.progress_bar.setVisible(False)
        self.list_report.clear()
        
        claims_selections = []
        specs_selections = []
        
        for issue in issues:
            item = QListWidgetItem(issue["text"])
            item.setData(Qt.ItemDataRole.UserRole, issue)
            self.list_report.addItem(item)
            
            span = issue.get("span", (0, 0))
            if span != (0, 0):
                selection = QTextEdit.ExtraSelection()
                fmt = QTextCharFormat()
                if "error" in issue.get("type", ""):
                    fmt.setBackground(QColor("#FF6B6B")) # 红色
                else:
                    fmt.setBackground(QColor("#FFD93D")) # 黄色
                fmt.setForeground(QColor("black"))
                selection.format = fmt
                
                target = issue.get("target", "claims")
                target_box = self.txt_specs if target == "specs" else self.txt_claims
                
                cursor = target_box.textCursor()
                cursor.setPosition(span[0])
                cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
                selection.cursor = cursor
                
                if target == "specs":
                    specs_selections.append(selection)
                else:
                    claims_selections.append(selection)
                    
        self.txt_claims.setExtraSelections(claims_selections)
        self.txt_specs.setExtraSelections(specs_selections)
            
        if not issues:
            self.list_report.addItem("恭喜！未在本文档中检测到明显的形缺或逻辑问题。")

    def on_report_double_clicked(self, item):
        issue = item.data(Qt.ItemDataRole.UserRole)
        if not issue: 
            return
            
        span = issue.get("span", (0, 0))
        if span == (0,0):
            return
            
        target = issue.get("target", "claims")
        target_box = self.txt_specs if target == "specs" else self.txt_claims
        
        cursor = target_box.textCursor()
        cursor.setPosition(span[0])
        cursor.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
        target_box.setTextCursor(cursor)
        target_box.setFocus()
        target_box.ensureCursorVisible()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
