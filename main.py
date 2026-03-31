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
from src.document_parser import parse_file, split_patent_document
from src.rules_checker import checker
from src.config import config
import src.config as conf_module

class RequireDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("设置 - 文本要求")
        self.resize(550, 480)
        layout = QVBoxLayout(self)
        
        info = QLabel("请设定以下锚点文本，它们将被用于自动分割和审查逻辑。\n如果不设定，自动分割将无法正常工作。")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # --- 增加填写示例区块 ---
        example_label = QLabel()
        example_label.setTextFormat(Qt.TextFormat.RichText)
        example_label.setText("""
        <div style='background-color: #f8f9fa; border: 1px solid #ced4da; padding: 10px; border-radius: 4px; margin-bottom: 5px;'>
            <p style='margin-top: 0; color: #2c3e50;'><b>💡 填写示例参考：</b></p>
            <table style='width: 100%; border-collapse: collapse;'>
                <tr>
                    <td style='width: 120px;'><b>权利要求开头：</b></td>
                    <td style='color: #d35400;'>1.一种XXXX，其特征在于，</td>
                </tr>
                <tr>
                    <td><b>说明书的开头：</b></td>
                    <td style='color: #d35400;'>技术领域</td>
                </tr>
                <tr>
                    <td><b>说明书的结尾：</b></td>
                    <td style='color: #d35400;'>并且这些变化或变型仍处于本发明的范围内。</td>
                </tr>
            </table>
        </div>
        """)
        layout.addWidget(example_label)
        
        # Claims start
        layout.addWidget(QLabel("权利要求书的开头 (例如: 1.一种XXXX，其特征在于，)："))
        self.edit_claims_start = QLineEdit()
        self.edit_claims_start.setPlaceholderText("示例: 1.一种XXXX，其特征在于，")
        layout.addWidget(self.edit_claims_start)
        
        # Specs start
        layout.addWidget(QLabel("说明书的开头 (例如: 技术领域)："))
        self.edit_specs_start = QLineEdit()
        self.edit_specs_start.setPlaceholderText("示例: 技术领域")
        layout.addWidget(self.edit_specs_start)
        
        # Specs end
        layout.addWidget(QLabel("说明书的结尾 (例如: 并且这些变化或变型仍处于本发明的范围内)："))
        self.edit_specs_end = QLineEdit()
        self.edit_specs_end.setPlaceholderText("示例: 并且这些变化或变型仍处于本发明的范围内。")
        layout.addWidget(self.edit_specs_end)
        
        # Load existing
        current = self.main_window.text_requirements
        self.edit_claims_start.setText(current.get("claims_start", ""))
        self.edit_specs_start.setText(current.get("specs_start", ""))
        self.edit_specs_end.setText(current.get("specs_end", ""))
        
        btn = QPushButton("保存")
        btn.clicked.connect(self.save_and_accept)
        layout.addWidget(btn)

    def save_and_accept(self):
        c_start = self.edit_claims_start.text().strip()
        s_start = self.edit_specs_start.text().strip()
        s_end = self.edit_specs_end.text().strip()
        
        if not c_start or not s_start or not s_end:
            QMessageBox.warning(self, "警告", "所有输入框均不能为空，请填写完整！")
            return
            
        self.main_window.text_requirements["claims_start"] = c_start
        self.main_window.text_requirements["specs_start"] = s_start
        self.main_window.text_requirements["specs_end"] = s_end
        
        self.main_window.save_settings()
        self.accept()


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
                self.main_window.save_settings()
            except Exception:
                pass


class DictEditDialog(QDialog):
    def __init__(self, dict_name, dict_path_var_name, description, format_req, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.dict_name = dict_name
        self.dict_path_var_name = dict_path_var_name
        self.setWindowTitle(f"编辑字典 - {dict_name}")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # 说明区域
        info_label = QLabel(f"<b>{dict_name}</b><br><br>{description}<br><br><b>格式要求：</b><br>{format_req}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        # 文本编辑区
        self.text_edit = QTextEdit()
        font = self.text_edit.font()
        font.setPointSize(11)
        self.text_edit.setFont(font)
        
        # 加载内容
        current_path = getattr(conf_module, self.dict_path_var_name, None)
        if current_path and os.path.exists(current_path):
            try:
                with open(current_path, "r", encoding="utf-8-sig") as f:
                    self.text_edit.setPlainText(f.read())
            except Exception as e:
                self.text_edit.setPlainText(f"读取异常: {e}")
                
        layout.addWidget(self.text_edit)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存并应用")
        btn_save.clicked.connect(self.save_dict)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
    def save_dict(self):
        # 防护：确保字典已经在外部准备好
        conf_module.ensure_external_dicts()
        # 路径可能在 ensures() 执行后变为外部路径，重新获取
        current_path = getattr(conf_module, self.dict_path_var_name)
        
        content = self.text_edit.toPlainText()
        try:
            with open(current_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 通知配置中心重载所有的正则和内存字典
            config.load_rules()
            QMessageBox.information(self, "成功", f"【{self.dict_name}】 已成功保存并立即生效！")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"发生了意外错误：{str(e)}")


class DictGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 - 字典使用指南 (0基础友好)")
        self.resize(850, 600)
        layout = QVBoxLayout(self)
        
        text = QTextEdit()
        text.setReadOnly(True)
        html_content = """
        <h2 style='color: #2c3e50; text-align: center;'>📖 专利审查字典 零基础补全指南</h2>
        <p>本系统内置了 8 个“大脑”字典，它们让电脑学会如何像审查员一样阅读。如果您想增加规则，请参考下表：</p>
        
        <table border="1" style="border-collapse: collapse; width: 100%; font-family: Microsoft YaHei; font-size: 14px;">
            <tr style="background-color: #34495e; color: white;">
                <th style='padding: 10px; width: 150px;'>字典类别</th>
                <th style='padding: 10px;'>通俗解释 (它是做什么的)</th>
                <th style='padding: 10px;'>补全格式 (你应该怎么写)</th>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>自定义分词</b><br>(userdict.txt)</td>
                <td style='padding: 10px;'><b>【大脑扩词卡】</b><br>专利中有很多专业术语（如“光刻模组”），电脑有时会把它拆散。在这里写下这些词，就是告诉电脑：这是一个完整的词。</td>
                <td style='padding: 10px;'>每行写一个词，空格后跟 3 n。<br>例：<code>光刻机 3 n</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>冗余词拦截</b><br>(useless_word.txt)</td>
                <td style='padding: 10px;'><b>【废话过滤器】</b><br>揪出“基本上”、“大概”等不严谨的口语词汇。让您的专利更具法律严肃性。</td>
                <td style='padding: 10px;'>每行写一行规则或词语。<br>例：<code>大概</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>法律红线词</b><br>(minganci.txt)</td>
                <td style='padding: 10px;'><b>【法律红线检测】</b><br>盯着“绝对”、“唯一”、“最好是”等极致词，防止权利要求范围被锁得太死或产生瑕疵。</td>
                <td style='padding: 10px;'>直接每行写下一个要禁用的词。<br>例：<code>极端高效</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>特征装配关联</b><br>(gudingdapei.txt)</td>
                <td style='padding: 10px;'><b>【关系捕捉器】</b><br>识别零件是怎么连接的（如“A固定在B上”）。电脑会核对：权利要求的连接逻辑在说明书里是否一致。</td>
                <td style='padding: 10px;'>用 <code>***</code> 代表零件。<br>例：<code>***垂直于***设置</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>方位空间逻辑</b><br>(weizhiguanxi.txt)</td>
                <td style='padding: 8px;'><b>【方位侦察兵】</b><br>专门提取“上面”、“内部”、“左侧”等方位词，辅助理顺机械零件之间的相对空间结构。</td>
                <td style='padding: 10px;'>同上，使用 <code>***</code> 锚定。<br>例：<code>***设在***的内部</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>别称映射表</b><br>(synonyms.txt)</td>
                <td style='padding: 10px;'><b>【别名对照表】</b><br>您一会儿叫它“螺钉”，一会儿叫它“紧固件”，电脑会犯晕。在这里告诉电脑它们其实是同一样东西。</td>
                <td style='padding: 10px;'>同行用英文逗号分隔。<br>例：<code>螺钉,螺栓,紧固件</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>步骤逻辑词</b><br>(transition_words.txt)</td>
                <td style='padding: 10px;'><b>【流程润滑剂】</b><br>识别“首先”、“接着”等步骤词，让电脑理清楚专利动作的执行顺序。</td>
                <td style='padding: 10px;'>每行写一个连接词。<br>例：<code>随后</code></td>
            </tr>
            <tr>
                <td style='padding: 10px; background-color: #ecf0f1;'><b>部件编号档案</b><br>(reference_signs.txt)</td>
                <td style='padding: 10px;'><b>【编号身份证】</b><br>记录“齿轮 10”等编号信息，这是检查“同名异号”或“异名同号”低级错误的关键。</td>
                <td style='padding: 10px;'>直接写入规则即可。</td>
            </tr>
        </table>
        <p style='color: #e67e22; font-weight: bold;'>温馨提示：您可以在“配置字典模型”中实时保存修改。修改后无需重启程序，审查引擎将立即更新！</p>
        """
        text.setHtml(html_content)
        layout.addWidget(text)
        
        btn = QPushButton("明白，我会补全了")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

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
        
        if getattr(sys, 'frozen', False):
            self.root_dir = os.path.dirname(sys.executable)
        else:
            self.root_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.settings_file = os.path.join(self.root_dir, "settings.json")
        self.current_theme = {
            "claims": "#ffffff",
            "specs": "#ffffff",
            "report": "#ffffff"
        }
        self.text_requirements = {
            "claims_start": "",
            "specs_start": "",
            "specs_end": ""
        }
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    
                    if "theme" in saved:
                        self.current_theme.update(saved["theme"])
                        self.text_requirements.update(saved.get("text_requirements", {}))
                    else:
                        # Legacy struct
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
        
        # --- 字典编辑子菜单 ---
        dicts_menu = settings_menu.addMenu("配置字典模型")
        
        # 增加说明入口
        action_dict_guide = QAction("📝 字典使用说明与规范", self)
        action_dict_guide.triggered.connect(self.show_dict_guide)
        dicts_menu.addAction(action_dict_guide)
        dicts_menu.addSeparator()
        
        dict_configs = [
            ("自定义分词库 (userdict)", "DICT_USER_PATH", "防止专有名词被错切分（例如“光刻机”被切成“光”、“刻机”）。", "每行一个词，后接词频和词类，空格分隔。例如：<br><code>光刻机 3 n<br>PCB板 3 n</code>"),
            ("冗余词拦截库 (useless_word)", "DICT_USELESS_PATH", "匹配并拦截由于口语化产生的不规范无意义词汇（如“大致”、“相关”）。", r"每行一条规则，支持基本正则表达式。例如：<br><code>大致<br>相关[\*\b]</code>"),
            ("敏感与防错库 (minganci)", "DICT_MINGANCI_PATH", "屏蔽极度主观的词汇或形缺严重错误语（如“绝对”、“完美”）。", "每行一条规则，支持基本正则表达式。例如：<br><code>绝对<br>完美</code>"),
            ("特征装配关联库 (gudingdapei)", "DICT_GUDINGDAPEI_PATH", "用于提取两个技术部件之间的安装配合、固定和拓扑连接关系。", "务必使用 <code>***</code> 代表前后的机械/虚拟核心部件名。例如：<br><code>***套设在***上方<br>与***螺纹连接</code>"),
            ("位置特征拦截库 (weizhiguanxi)", "DICT_WEIZHI_PATH", "独立抽取表示方位的介词结构，辅助识别空间关联。", "类似于上述特征搭配，也必须使用 <code>***</code> 锚定对象。例如：<br><code>***位于***上方</code>"),
            ("同义词对照库 (synonyms)", "DICT_SYNONYMS_PATH", "审查权利要求特征在说明书中寻找“对应支撑”时的主动同义词扩散。", "必须在同一行使用英文逗号分隔所有同义别称。例如：<br><code>螺钉,螺栓,紧固件<br>壳体,外壳,机壳</code>")
        ]
        
        for name, var_name, desc, req in dict_configs:
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, n=name, v=var_name, d=desc, r=req: self.open_dict_editor(n, v, d, r))
            dicts_menu.addAction(action)
            
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
        
        # 将配置中的正则预装到 Highlighter (红色底)
        if config.minganci_regex:
            qregex = QRegularExpression(config.minganci_regex.pattern)
            self.highlighter_claims.set_rules([qregex], QColor("#FF6B6B"))
            self.highlighter_specs.set_rules([qregex], QColor("#FF6B6B"))

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

    def open_dict_editor(self, name, var_name, desc, req):
        dialog = DictEditDialog(name, var_name, desc, req, self, self)
        dialog.exec()

    def show_dict_guide(self):
        diag = DictGuideDialog(self)
        diag.exec()

    def show_text_requirements(self):
        diag = RequireDialog(self, parent=self)
        diag.exec()
        
    def save_settings(self):
        saved = {
            "theme": self.current_theme,
            "text_requirements": self.text_requirements
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def check_requirements_filled(self):
        reqs = self.text_requirements
        if not reqs.get("claims_start") or not reqs.get("specs_start") or not reqs.get("specs_end"):
            QMessageBox.information(self, "提示", "请先完善『文本要求』设置中的分割锚点，再进行各项操作！")
            diag = RequireDialog(self, parent=self)
            if diag.exec() != QDialog.DialogCode.Accepted:
                return False
        return True
        
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
        if not self.check_requirements_filled():
            return
            
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
            full_text = parse_file(file_path)
            result = split_patent_document(full_text, self.text_requirements)
            
            if not result["claims"] and not result["specification"]:
                QMessageBox.warning(self, "分割失败", "自动分割失败：无法准确定位【权利要求】与【技术领域】锚点。请您手动复制原文至对应文本框内！")
                self.txt_claims.setText(full_text)
                self.txt_specs.clear()
            else:
                self.txt_claims.setText(result["claims"])
                self.txt_specs.setText(result["specification"])
                
            self.btn_check.setEnabled(True)
            self.list_report.addItem("> 文档分割完成！如果不准请手动截断复制修正，确认无误后请点击「开始形式审查」。")
            self.update_stats()

        except Exception as e:
            self.list_report.addItem(f"❌ 读取错误: {str(e)}")

    def run_checks(self):
        if not self.check_requirements_filled():
            return
            
        self.claims_text = self.txt_claims.toPlainText()
        self.specs_text = self.txt_specs.toPlainText()
        
        if not self.claims_text or not self.specs_text:
            QMessageBox.warning(self, "警告", "请确保两侧都有文本内容！")
            return
            
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()

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
