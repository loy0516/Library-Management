import os
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QPushButton,
    QComboBox, QTabWidget, QHBoxLayout, QLineEdit, QSpacerItem, QSizePolicy,
    QTableWidget, QTableWidgetItem, QDialog, QMessageBox, QHeaderView, QGridLayout
)
from PySide6.QtCore import QByteArray, QBuffer, QSize, Qt
from PySide6.QtGui import QMovie, QIntValidator

# 你的核心模块导入
import core.book_baidu
import core.book_index
import core.book_jiajia
import core.book_modify


# ----------------------------------------------------
# ⭐️ 详情修改窗口类 (BookDetailDialog) ⭐️
# ----------------------------------------------------

class BookDetailDialog(QDialog):
    def __init__(self, mother_id, parent=None):
        super().__init__(parent)
        self.mother_id = mother_id
        # 防止 parent 没有 db 属性报错
        self.db = parent.db if hasattr(parent, 'db') else None
        self.page_size = 20  # 副本表默认每页显示条数
        self.current_page = 1
        self.total_copy_pages = 1
        self.all_copies = []  # 存储所有副本数据
        self.current_mother_keys = []  # 存储当前显示的图书原始键名列表，用于修改时查找

        # ⭐️ 副本信息的中英文映射 (新增/保持)
        self.copy_key_translation = {
            "copy_id": "副本ID",  # 必须添加！
            "status": "状态",
            "borrower_name": "借书人",  # 数据库实际键名
            "borrow_date": "借书时间",
            "due_date": "应还时间",
            "notes": "备注",  # 数据库实际键名
        }
        # ⭐️ 关键：初始化时就确定副本的英文键名顺序
        self.current_copy_keys = list(self.copy_key_translation.keys())

        # ⭐️ 新增：数据库键名映射字典 (用于 on_copy_item_changed 保存时使用)
        self.db_key_map = {
            'copy_id': 'copy_id',
            'status': 'status',
            'borrower_name': 'borrower_name',  # UI键名 -> DB键名
            'borrow_date': 'borrow_date',
            'due_date': 'due_date',
            'notes': 'notes',  # UI键名 -> DB键名
        }

        self.setWindowTitle(f"图书详情 - ID: {mother_id}")
        self.resize(1300, 850)

        # --- 布局和控件初始化 ---
        main_layout = QVBoxLayout(self)

        # 1. 🌟 图书信息表格 (固定 1 行显示值，表头显示中文)
        main_layout.addWidget(QLabel("📚 图书详细信息(双击修改)："))
        self.mother_table = QTableWidget()
        self.mother_table.setRowCount(1)
        self.mother_table.setMaximumHeight(80)
        self.mother_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mother_table.setEditTriggers(QTableWidget.DoubleClicked)
        main_layout.addWidget(self.mother_table)

        # 2. 🌟 副本信息表格
        main_layout.addWidget(QLabel("📖 副本列表 (双击修改)："))
        self.copy_table = QTableWidget()
        self.copy_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.copy_table.setEditTriggers(QTableWidget.DoubleClicked)
        main_layout.addWidget(self.copy_table)

        # 3. 分页控件
        self.setup_pagination_controls(main_layout)

        # 4. 绑定事件
        self.mother_table.itemChanged.connect(self.on_mother_item_changed)
        self.copy_table.itemChanged.connect(self.on_copy_item_changed)

        # 5. 加载数据
        self.load_and_display_data()

    def setup_pagination_controls(self, layout):
        """设置详情窗口的分页控件布局"""
        self.pagination_layout = QHBoxLayout()

        self.prev_page_button = QPushButton("◀ 上一副本页")
        self.prev_page_button.clicked.connect(self.on_page_prev)
        self.pagination_layout.addWidget(self.prev_page_button)

        self.page_info_label = QLabel("副本页码: 1 / 1")
        self.pagination_layout.addWidget(self.page_info_label)

        self.next_page_button = QPushButton("下一副本页 ▶")
        self.next_page_button.clicked.connect(self.on_page_next)
        self.pagination_layout.addWidget(self.next_page_button)

        self.pagination_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.page_size_label = QLabel("每页副本:")
        self.pagination_layout.addWidget(self.page_size_label)

        self.page_size_input = QLineEdit(str(self.page_size))
        self.page_size_input.setValidator(QIntValidator(1, 999, self))
        self.page_size_input.setFixedWidth(50)
        self.page_size_input.editingFinished.connect(self._on_page_size_changed)
        self.pagination_layout.addWidget(self.page_size_input)

        self.pagination_layout.addWidget(QLabel("条"))

        layout.addLayout(self.pagination_layout)

    def load_and_display_data(self):
        """加载图书和副本数据，并分别显示。"""
        try:
            # 1. 获取图书信息 (用于填充图书表格)
            mother_info = core.book_baidu.get_book_record_by_id(self.mother_id)
        except Exception as e:
            QMessageBox.critical(self, "数据加载错误", f"无法加载图书信息: {e}")
            mother_info = None

        # 2. ⭐️ 关键修改：获取副本数据 (使用 get_all_copies_by_mother_id_optimized)
        try:
            raw_copies = core.book_baidu.get_all_copies_by_mother_id_optimized(self.mother_id)

        except AttributeError:
            print("警告: 缺少 core.book_baidu.get_all_copies_by_mother_id_optimized 方法。")
            raw_copies = []
        except Exception as e:
            print(f"获取副本数据时发生错误: {e}")
            raw_copies = []

        # 3. 副本数据标准化
        self.all_copies = []
        if raw_copies and isinstance(raw_copies, list):
            for copy_data in raw_copies:
                if isinstance(copy_data, dict):
                    # 确保每个副本数据字典都包含所有目标键，并赋予空值作为默认值
                    full_copy_data = {}
                    for key in self.current_copy_keys:
                        # 使用 get() 方法，如果数据中没有该键，则使用空字符串
                        full_copy_data[key] = copy_data.get(key, '')
                    self.all_copies.append(full_copy_data)

        # 4. 图书信息模拟数据 (如果数据库返回空，防止界面空白)
        if not mother_info:
            mother_info = {'book_id': self.mother_id, 'name': '未找到数据', 'author': 'N/A',
                           'publisher': 'N/A'}

        # 5. 显示数据
        self.display_mother_info(mother_info)
        self.display_copy_info()

    def display_mother_info(self, mother_info):
        """
        填充并设置图书信息表格，使用中文表头。
        """
        table = self.mother_table

        # ⭐️ 1. 定义中英文映射字典
        key_translation = {
            "name": "书名",
            "author": "作者",
            "publisher": "出版社",
            "isbn": "ISBN",
            "pages": "页数",
            "words": "字数",
            "category": "类别",
            "quantity": "入库数",
            "date_added": "入库时间"
        }

        # 排除 'copies' 键
        self.current_mother_keys = [k for k in mother_info.keys() if k != 'copies']

        # ⭐️ 2. 生成中文表头列表
        header_labels = []
        for key in self.current_mother_keys:
            # 如果字典里有翻译就用中文，没有就用原英文
            header_labels.append(key_translation.get(key, key))

        # 设置列数和表头
        num_cols = len(self.current_mother_keys)
        table.setColumnCount(num_cols)
        table.setHorizontalHeaderLabels(header_labels)

        # 标志定义
        NON_EDITABLE_FLAGS = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        EDITABLE_FLAGS = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

        # ⭐️ 3. 填充数据 (只填充第 0 行)
        for col, key in enumerate(self.current_mother_keys):
            value = str(mother_info.get(key, ''))
            val_item = QTableWidgetItem(value)

            if key == 'book_id':
                val_item.setFlags(NON_EDITABLE_FLAGS)  # ID 不可改
                # 可以给ID加个背景色提示不可改
                val_item.setBackground(Qt.lightGray)
            else:
                val_item.setFlags(EDITABLE_FLAGS)

            # 设置到第 0 行
            table.setItem(0, col, val_item)

    def display_copy_info(self):
        """
        填充并设置副本信息表格 (self.copy_table)，使用自定义中文表头。
        """
        table = self.copy_table

        # 1. 更新分页状态
        self.update_pagination_controls(len(self.all_copies))

        # 2. 计算当前页数据
        start_index = (self.current_page - 1) * self.page_size
        end_index = start_index + self.page_size
        page_copies = self.all_copies[start_index:end_index]

        # 1. 设置列头和行数 (关键!)
        header_labels = [self.copy_key_translation[key] for key in self.current_copy_keys]
        table.setColumnCount(len(self.current_copy_keys))
        table.setHorizontalHeaderLabels(header_labels)
        table.setRowCount(len(page_copies))  # ⭐️ 确保行数正确设置

        # ⭐️ 新增：隐藏第 0 列 (即 副本ID 列)
        table.setColumnHidden(0, True)

        # 标志定义
        NON_EDITABLE_FLAGS = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        EDITABLE_FLAGS = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

        # 4. 填充数据
        for row, copy_info in enumerate(page_copies):
            for col, key in enumerate(self.current_copy_keys):
                value = str(copy_info.get(key, ''))
                item = QTableWidgetItem(value)

                # 副本 ID ('copy_id') 不可修改
                if key == 'copy_id':
                    item.setFlags(NON_EDITABLE_FLAGS)
                    item.setBackground(Qt.lightGray)
                else:
                    item.setFlags(EDITABLE_FLAGS)

                table.setItem(row, col, item)
        table.viewport().update()

    def update_pagination_controls(self, total_results):
        """更新副本分页控件"""
        self.total_copy_pages = (total_results + self.page_size - 1) // self.page_size

        if self.total_copy_pages == 0: self.total_copy_pages = 1
        if self.current_page > self.total_copy_pages: self.current_page = self.total_copy_pages

        self.page_info_label.setText(f"副本页码: {self.current_page} / {self.total_copy_pages}")
        self.prev_page_button.setEnabled(self.current_page > 1)
        self.next_page_button.setEnabled(self.current_page < self.total_copy_pages)

    def on_page_prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_copy_info()

    def on_page_next(self):
        if self.current_page < self.total_copy_pages:
            self.current_page += 1
            self.display_copy_info()

    def _on_page_size_changed(self):
        try:
            new_size = int(self.page_size_input.text().strip())
            if 1 <= new_size <= 999:
                self.page_size = new_size
                self.current_page = 1
                self.display_copy_info()
            else:
                self.page_size_input.setText(str(self.page_size))
        except ValueError:
            self.page_size_input.setText(str(self.page_size))

    def on_mother_item_changed(self, item):
        """图书表格修改事件"""
        # 只有第 0 行可修改
        if item.row() == 0:
            col = item.column()

            # 避免在表格加载数据时触发保存
            if item.text() == "":
                return

            if col < len(self.current_mother_keys):
                key = self.current_mother_keys[col]
                val = item.text()

                print(f"✅ 自动保存图书: ID={self.mother_id}, Key={key}, NewValue={val}")

                # ⭐️ 实际调用：更新图书字段
                try:
                    success = core.book_jiajia.update_mother_field(self.mother_id, key, val)
                    if success:
                        # 可选：更新本地数据（通常不需要，因为图书详情不常变动）
                        # QMessageBox.information(self, "成功", f"图书字段 {key} 已保存。")
                        pass
                    else:
                        QMessageBox.warning(self, "保存失败", f"图书字段 {key} 保存到数据库失败。")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存图书数据时发生异常: {e}")

    def on_copy_item_changed(self, item):
        """
        副本表格修改事件。直接从表格的第 0 列获取隐藏的 copy_id，并使用数据库键名进行保存。
        """
        row = item.row()
        col = item.column()
        val = item.text()

        # 1. ⭐️ 核心修正：直接从表格的第 0 列获取完整的副本 ID
        copy_id_item = self.copy_table.item(row, 0)
        if copy_id_item is None:
            print("🛑 错误: 无法从表格第0列获取副本ID项。保存失败。")
            return

        copy_id = copy_id_item.text()  # 提取完整的副本 ID

        # 2. 从 self.current_copy_keys 获取 UI/DB 键名
        if col < len(self.current_copy_keys):
            db_key = self.current_copy_keys[col]  # 这里的键名已经是 DB 键名 (e.g., 'borrower_name')
        else:
            return

        # 3. 避免表格加载数据时触发保存
        # 注意：我们必须从 self.all_copies 获取数据来进行值校验和同步
        start_index = (self.current_page - 1) * self.page_size
        global_index = start_index + row
        current_data = self.all_copies[global_index]

        # 检查值是否改变
        if str(current_data.get(db_key, '')) == val:
            return

        # 4. 如果尝试修改 ID 自身，则阻止
        if db_key == 'copy_id':
            QMessageBox.warning(self, "禁止操作", "副本ID无法直接修改。")
            return

        # 5. 执行保存操作
        print(f"✅ 自动保存副本: ID={copy_id}, DB_Key={db_key}, NewValue={val}")

        try:
            # 实际调用：更新副本字段 (使用 DB 键名和完整的 copy_id)
            success = core.book_jiajia.update_copy_field(copy_id, db_key, val)

            if success:
                # ⭐️ 数据同步：更新本地列表中的副本数据
                current_data[db_key] = val
            else:
                QMessageBox.warning(self, "保存失败", f"副本 {copy_id} 字段 {db_key} 保存到数据库失败。")
                # 失败时可以考虑恢复表格原始值
                # item.setText(str(current_data.get(db_key, '')))

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存副本数据时发生异常: {e}")


# ----------------------------------------------------
# ⭐️ book_root 主窗口类 ⭐️
# ----------------------------------------------------

class book_root(QWidget):
    def __init__(self):
        super().__init__()
        # 查找文件夹是否存在
        try:
            core.book_jiajia.book_pach()
        except Exception as e:
            QMessageBox.critical(self, "初始化错误", f"文件夹检查失败: {e}")

        # 生成索引
        try:
            core.book_index.input_oput_index()
        except Exception as e:
            QMessageBox.critical(self, "初始化错误", f"索引生成失败: {e}")

        # 核心变量
        self.current_search_results = {}
        self.page_size = 10
        self.current_page = 1
        self.total_pages = 1

        self.setWindowTitle("图书管理系统")
        self.setGeometry(100, 100, 600, 400)

        self.tab_widget = QTabWidget(self)

        # 页面 1: 信息展示
        self.info_page = QWidget()
        self.info_layout = QVBoxLayout()
        self.info_label = QLabel("欢迎使用 图书管理系统！\n\t\t\tby.tornado")
        self.info_layout.addWidget(self.info_label)
        self.info_page.setLayout(self.info_layout)

        # 页面 2: 添加书籍
        self.add_book_page = QWidget()
        self.setup_add_book_ui()  # 调用封装好的 UI 初始化

        # 页面 3: 搜索书籍
        self.search_book_page = QWidget()
        self.search_book_layout = QVBoxLayout()
        self.search_book_layout.setAlignment(Qt.AlignTop)

        # 3.1 筛选栏
        self.filter_layout = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItem("类别筛选")
        self.category_filter.addItem("所有分类")
        self.filter_layout.addWidget(self.category_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItem("状态筛选")
        self.status_filter.addItem("所有状态")
        self.status_filter.addItem("正常")
        self.status_filter.addItem("借出")
        self.status_filter.addItem("丢失")
        self.status_filter.addItem("损坏")
        self.status_filter.addItem("下架")
        self.filter_layout.addWidget(self.status_filter)

        self.populate_filters_from_index()
        self.category_filter.currentIndexChanged.connect(self.on_filter_changed)
        self.status_filter.currentIndexChanged.connect(self.on_filter_changed)

        self.input_filter = QLineEdit()
        self.input_filter.setPlaceholderText("请输入搜索内容（书名第一个字/作者）")
        self.filter_layout.addWidget(self.input_filter)

        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.on_search)
        self.filter_layout.addWidget(self.search_button)
        self.search_book_layout.addLayout(self.filter_layout)

        # 3.2 搜索结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)  # ID, 书名, 作者, 出版社, 分类, 副本数
        self.result_table.setHorizontalHeaderLabels(['ID', '书名', '作者', '出版社', '分类', '副本数'])
        # 设置列宽模式为 Stretch (固定比例，不随内容变)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 连接双击事件
        self.result_table.cellDoubleClicked.connect(self.on_result_double_clicked)
        self.search_book_layout.addWidget(self.result_table)

        # 3.3 分页控制
        self.pagination_layout = QHBoxLayout()
        self.prev_page_button = QPushButton("◀ 上一页")
        self.prev_page_button.clicked.connect(self.on_prev_page)
        self.pagination_layout.addWidget(self.prev_page_button)

        self.page_info_label = QLabel("第 1 / 1 页")
        self.pagination_layout.addWidget(self.page_info_label)

        self.next_page_button = QPushButton("下一页 ▶")
        self.next_page_button.clicked.connect(self.on_next_page)
        self.pagination_layout.addWidget(self.next_page_button)

        self.pagination_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.page_size_label = QLabel("双击文件进入详情     每页显示:")
        self.pagination_layout.addWidget(self.page_size_label)
        self.page_size_input = QLineEdit(str(self.page_size))
        self.page_size_input.setValidator(QIntValidator(1, 999, self))
        self.page_size_input.setFixedWidth(50)
        self.page_size_input.editingFinished.connect(self.on_page_size_changed)
        self.pagination_layout.addWidget(self.page_size_input)
        self.pagination_layout.addWidget(QLabel("条"))

        self.search_book_layout.addLayout(self.pagination_layout)
        self.search_book_page.setLayout(self.search_book_layout)

        # 初始化 Tab
        self.tab_widget.addTab(self.info_page, "信息展示")
        self.tab_widget.addTab(self.add_book_page, "添加书籍")
        self.tab_widget.addTab(self.search_book_page, "操作书籍")

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tab_widget)
        self.setLayout(self.layout)

    def setup_add_book_ui(self):
        """初始化添加书籍页面控件，包含 GIF"""
        self.add_book_layout = QVBoxLayout()
        self.add_book_layout.setAlignment(Qt.AlignTop)

        # 书名
        self.add_book_label_title = QLabel("输入书名:")
        self.addinput_title = QLineEdit()
        self.addinput_title.setPlaceholderText("时间简史")
        self.addinput_title.setFixedWidth(200)
        # 作者
        self.add_book_label_author = QLabel("输入作者:")
        self.addinput_author = QLineEdit()
        self.addinput_author.setPlaceholderText("斯蒂芬·霍金")
        self.addinput_author.setFixedWidth(200)
        # 出版社
        self.add_book_label_publisher = QLabel("输入出版社:")
        self.addinput_publisher = QLineEdit()
        self.addinput_publisher.setPlaceholderText("宇宙出版社")
        self.addinput_publisher.setFixedWidth(200)
        # isbn
        self.add_book_label_isbn = QLabel("输入ISBN:")
        self.addinput_isbn = QLineEdit()
        self.addinput_isbn.setPlaceholderText("978-0-123456-78-9")
        self.addinput_isbn.setFixedWidth(200)
        # 页数
        self.add_book_label_pages = QLabel("输入页数:")
        self.addinput_pages = QLineEdit()
        self.addinput_pages.setPlaceholderText("320")
        self.addinput_pages.setFixedWidth(200)
        self.addinput_pages.setValidator(QIntValidator(1, 99999, self))
        # 字数
        self.add_book_label_words = QLabel("输入字数:")
        self.addinput_words = QLineEdit()
        self.addinput_words.setPlaceholderText("20万字")
        self.addinput_words.setFixedWidth(200)
        # 类别
        self.add_book_label_category = QLabel("输入类别:")
        self.addinput_category = QLineEdit()
        self.addinput_category.setPlaceholderText("科学")
        self.addinput_category.setFixedWidth(200)
        # 数量
        self.add_book_label_quantity = QLabel("输入入库本数:")
        self.addinput_quantity = QLineEdit()
        self.addinput_quantity.setPlaceholderText("5")
        self.addinput_quantity.setFixedWidth(150)
        self.addinput_quantity.setValidator(QIntValidator(1, 9999, self))
        # 添加按钮
        self.add_button = QPushButton("添加")
        self.add_button.setFixedWidth(200)
        self.add_button.clicked.connect(self.on_add_book)

        self.add_book_layout.addWidget(self.add_book_label_title)
        self.add_book_layout.addWidget(self.addinput_title)
        self.add_book_layout.addWidget(self.add_book_label_author)
        self.add_book_layout.addWidget(self.addinput_author)
        self.add_book_layout.addWidget(self.add_book_label_publisher)
        self.add_book_layout.addWidget(self.addinput_publisher)
        self.add_book_layout.addWidget(self.add_book_label_isbn)
        self.add_book_layout.addWidget(self.addinput_isbn)
        self.add_book_layout.addWidget(self.add_book_label_pages)
        self.add_book_layout.addWidget(self.addinput_pages)
        self.add_book_layout.addWidget(self.add_book_label_words)
        self.add_book_layout.addWidget(self.addinput_words)
        self.add_book_layout.addWidget(self.add_book_label_category)
        self.add_book_layout.addWidget(self.addinput_category)
        self.add_book_layout.addWidget(self.add_book_label_quantity)
        self.add_book_layout.addWidget(self.addinput_quantity)
        self.add_book_layout.addWidget(self.add_button)

        # ----------------------------------------------------
        # ⭐️ 恢复 GIF 动画加载与布局 ⭐️
        # ----------------------------------------------------
        try:
            gif_data = core.book_modify.gif()
            if not gif_data:
                raise ValueError("core.book_modify.gif() 返回了空数据。")

            self.gif_byte_array = QByteArray(gif_data)
            self.buffer = QBuffer(self.gif_byte_array)
            self.buffer.open(QBuffer.ReadOnly)

            self.gif_label = QLabel()
            self.gif_label.setFixedSize(300, 300)
            self.gif_label.setScaledContents(True)

            self.movie = QMovie(self.buffer)
            self.movie.setScaledSize(QSize(300, 300))

            if self.movie.isValid():
                self.gif_label.setMovie(self.movie)
                self.movie.start()
            else:
                self.gif_label.setText("GIF 加载失败")

        except Exception as e:
            print(f"GIF 加载错误: {e}")
            self.gif_label = QLabel("GIF 加载失败，请检查 core.book_modify.gif()")
            self.gif_label.setFixedSize(300, 300)
            self.gif_label.setAlignment(Qt.AlignCenter)

        # 垂直布局来控制 GIF 的位置（使其偏下一点）
        self.gif_vertical_layout = QVBoxLayout()
        self.gif_vertical_layout.addSpacing(40)
        self.gif_vertical_layout.addWidget(self.gif_label)
        self.gif_vertical_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # 创建水平布局，将输入框布局和 GIF 布局放在一起
        self.add_book_horizontal_layout = QHBoxLayout()
        self.add_book_horizontal_layout.addLayout(self.add_book_layout)
        self.add_book_horizontal_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))
        self.add_book_horizontal_layout.addLayout(self.gif_vertical_layout)
        self.add_book_horizontal_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 设置添加书籍页面的最终布局
        self.add_book_page.setLayout(self.add_book_horizontal_layout)

    def on_add_book(self):
        """
        处理添加书籍的逻辑：
        1. 校验必填项和数量格式。
        2. 调用核心函数 core.book_jiajia.add_db 进行数据写入。
        3. 根据结果弹出提示框（成功/失败/错误）。
        4. 成功后更新索引并清理输入框。
        """
        book_title = self.addinput_title.text().strip()
        quantity_text = self.addinput_quantity.text().strip()

        # 1. 校验必填项 (书名和数量)
        if not book_title:
            QMessageBox.warning(self, "输入校验", "书名不能为空。")
            return

        if not quantity_text:
            QMessageBox.warning(self, "输入校验", "入库本数不能为空。")
            return

        # 2. 校验数量格式
        try:
            # 使用 QLineEdit 的 QIntValidator 已经做了大部分校验，但这里再次确认以防止意外。
            quantity = int(quantity_text)
            if quantity <= 0:
                QMessageBox.warning(self, "输入校验", "入库本数必须大于 0。")
                return
        except ValueError:
            QMessageBox.critical(self, "输入错误", "入库本数必须是有效的整数。")
            return

        # 3. 调用核心添加函数并处理结果
        try:
            # 假设 core.book_jiajia.add_db 成功时返回 True
            success = core.book_jiajia.add_db(
                book_title,
                self.addinput_author.text().strip(),
                self.addinput_publisher.text().strip(),
                self.addinput_isbn.text().strip(),
                self.addinput_pages.text().strip(),
                self.addinput_words.text().strip(),
                self.addinput_category.text().strip(),
                quantity_text  # 注意：如果 core.book_jiajia.add_db 内部需要字符串，则传 quantity_text
                # 如果需要整数，则传 quantity
                # 这里暂时保持原函数传入的字符串形式
            )

            # 4. 根据结果弹出提示框
            if success:
                # 成功操作
                core.book_index.input_oput_index()  # 必须更新索引

                QMessageBox.information(self, "操作成功",
                                        f"书籍 '{book_title}' 及 {quantity} 个副本已成功添加！")

                # 清空输入框
                self.addinput_title.clear()
                self.addinput_author.clear()
                self.addinput_publisher.clear()
                self.addinput_isbn.clear()
                self.addinput_pages.clear()
                self.addinput_words.clear()
                self.addinput_category.clear()
                self.addinput_quantity.clear()

                # 刷新搜索结果 (可选)
                self.tab_widget.setCurrentIndex(2)  # 切换到操作书籍页
                self.on_search()

            else:
                # 核心函数返回 False (逻辑失败)
                QMessageBox.warning(self, "添加失败",
                                    "书籍添加操作未成功完成，请检查核心模块的返回结果。")

        except Exception as e:
            # 核心模块抛出异常 (系统错误)
            QMessageBox.critical(self, "系统错误",
                                 f"添加书籍时发生致命异常：{e}")
            print(f"添加书籍时发生错误: {e}")

    def populate_filters_from_index(self):
        try:
            db_pach = core.book_modify.book_pach_index()
            index_pach_class = os.path.join(db_pach, "book-class-index.json")
            index_pach_status = os.path.join(db_pach, "book-status-index.json")

            class_index = core.book_baidu.read_json_file(index_pach_class)
            while self.category_filter.count() > 2: self.category_filter.removeItem(2)
            for cat in sorted(class_index.keys()): self.category_filter.addItem(cat)

            status_index = core.book_baidu.read_json_file(index_pach_status)
            while self.status_filter.count() > 7: self.status_filter.removeItem(7)
            core_statuses = {"正常", "借出", "丢失", "损坏", "下架"}
            for s in sorted(list(set(status_index.keys()) - core_statuses)): self.status_filter.addItem(s)
        except Exception as e:
            QMessageBox.critical(self, "索引加载错误", f"加载索引文件时发生错误：{e}")

    def on_filter_changed(self):
        self.on_search()

    def filter_data_with_index(self, category, status, initial_ids=None):
        try:
            db_pach = core.book_modify.book_pach_index()
            index_pach_class = os.path.join(db_pach, "book-class-index.json")
            index_pach_status = os.path.join(db_pach, "book-status-index.json")

            if initial_ids is not None:
                final_mother_ids = initial_ids.copy()
                all_class_index = core.book_baidu.read_json_file(index_pach_class)
            else:
                all_class_index = core.book_baidu.read_json_file(index_pach_class)
                final_mother_ids = set(mid for ids in all_class_index.values() for mid in ids)

            if not final_mother_ids: return {}

            if category != "所有分类":
                category_matches = set(all_class_index.get(category, []))
                final_mother_ids = final_mother_ids.intersection(category_matches)
                if not final_mother_ids: return {}

            if status != "所有状态":
                status_index = core.book_baidu.read_json_file(index_pach_status)
                status_copy_matches = set(status_index.get(status, []))
                if not status_copy_matches: return {}
                status_mother_ids = set('-'.join(cid.split('-')[:-1]) for cid in status_copy_matches)
                final_mother_ids = final_mother_ids.intersection(status_mother_ids)

            filtered_books_data = {}
            for mid in final_mother_ids:
                book_info = core.book_baidu.get_book_record_by_id(mid)
                if book_info: filtered_books_data[mid] = book_info
            return filtered_books_data
        except Exception as e:
            QMessageBox.critical(self, "数据过滤错误", f"执行数据过滤或读取时发生错误：{e}")
            return {}  # 返回空结果，防止程序崩溃

    def on_search(self):
        try:
            db_pach = core.book_modify.book_pach_index()
            index_pach_name = os.path.join(db_pach, "book-name-index.json")
            index_pach_zuozhe = os.path.join(db_pach, "book-zuozhe-index.json")

            search_term = self.input_filter.text().strip()
            selected_category = self.category_filter.currentText()
            selected_status = self.status_filter.currentText()

            category_filter = selected_category if selected_category != "类别筛选" else "所有分类"
            status_filter = selected_status if selected_status != "状态筛选" else "所有状态"

            initial_ids = None
            if search_term:
                name_index = core.book_baidu.read_json_file(index_pach_name)
                zuozhe_index = core.book_baidu.read_json_file(index_pach_zuozhe)
                initial_ids = set(name_index.get(search_term, [])).union(set(zuozhe_index.get(search_term, [])))
                if not initial_ids and (category_filter == "所有分类" and status_filter == "所有状态"):
                    self.current_search_results = {}
                    self.current_page = 1
                    self.display_search_results()
                    return

            self.current_search_results = self.filter_data_with_index(category_filter, status_filter, initial_ids)
            self.current_page = 1
            self.display_search_results()
        except Exception as e:
            QMessageBox.critical(self, "搜索索引错误", f"读取搜索索引文件时发生错误：{e}")
            self.current_search_results = {}
            self.current_page = 1
            self.display_search_results()

    def display_search_results(self):
        self.update_pagination_controls()
        start = (self.current_page - 1) * self.page_size
        end = start + self.page_size
        result_items = list(self.current_search_results.items())
        page_items = result_items[start:end]

        self.result_table.setRowCount(0)
        if not page_items: return

        self.result_table.setRowCount(len(page_items))

        # 标志：可选，可用，但不可编辑
        NON_EDITABLE_FLAGS = Qt.ItemIsSelectable | Qt.ItemIsEnabled

        for row, (mid, info) in enumerate(page_items):
            # 准备数据：ID, 书名, 作者, 出版社, 分类, 副本数
            data = [
                mid,
                info.get('name', ''),
                info.get('author', ''),
                info.get('publisher', ''),
                info.get('category', ''),
                str(len(info.get('copies', [])))
            ]

            for col, val in enumerate(data):
                item = QTableWidgetItem(str(val))
                item.setFlags(NON_EDITABLE_FLAGS)  # 禁止主列表修改
                self.result_table.setItem(row, col, item)

    def on_page_size_changed(self):
        try:
            self.page_size = int(self.page_size_input.text().strip())
            self.current_page = 1
            self.display_search_results()
        except:
            pass

    def on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_search_results()

    def on_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.display_search_results()

    def update_pagination_controls(self):
        total = len(self.current_search_results)
        self.total_pages = (total + self.page_size - 1) // self.page_size
        if self.total_pages == 0: self.total_pages = 1
        if self.current_page > self.total_pages: self.current_page = self.total_pages

        self.page_info_label.setText(f"第 {self.current_page} / {self.total_pages} 页")
        self.prev_page_button.setEnabled(self.current_page > 1)
        self.next_page_button.setEnabled(self.current_page < self.total_pages)

    def on_result_double_clicked(self, row, column):
        # 直接获取第0列的ID
        mid_item = self.result_table.item(row, 0)
        if mid_item:
            BookDetailDialog(mid_item.text(), self).exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = book_root()
    window.show()
    sys.exit(app.exec())
