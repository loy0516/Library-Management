import json
import os
from .book_baidu import read_json_files_in_directory
from .book_modify import book_pach_index
from .book_modify import book_pach_db_data, book_pach_db_data_b


def generate_index(data, data_b):
    # 初始化索引字典
    book_name_index = {}
    book_class_index = {}
    book_status_index = {}
    book_zuozhe_index = {}
    # ⭐️ 修正 1：将 book_sw_index 重命名为 book_copy_boundary_index 并初始化
    book_copy_boundary_index = {}

    # 获取母本内容
    mother_books_data = read_json_files_in_directory(data)

    # 获取副本内容
    copies_data = read_json_files_in_directory(data_b)

    # ----------------------------------------------------
    # 1. 遍历母本数据，生成书名、作者、类别索引
    # ----------------------------------------------------
    for i in mother_books_data:
        for book_file, book_info in i.items():
            book_title_first_char = book_info["name"][0]  # 获取书名的第一个字
            author = book_info.get("author", "未知作者")
            category = book_info.get("category", "未知类别")

            # 书名索引（第一个字）
            if book_title_first_char:
                if book_title_first_char not in book_name_index:
                    book_name_index[book_title_first_char] = []
                book_name_index[book_title_first_char].append(book_file)

            # 作者索引
            if author:
                if author not in book_zuozhe_index:
                    book_zuozhe_index[author] = []
                book_zuozhe_index[author].append(book_file)

            # 类别索引
            if category:
                if category not in book_class_index:
                    book_class_index[category] = []
                book_class_index[category].append(book_file)

    # ----------------------------------------------------
    # 2. 遍历副本数据，生成状态索引和边界索引
    # ----------------------------------------------------
    file_num = 1  # ⭐️ 文件计数器，从 1 开始对应 book-b-1.json

    # 遍历所有书籍副本 (copies_data 列表的每个元素都是一个文件的内容字典)
    for copy_records_dict in copies_data:
        # copy_records_dict: 即该文件内的所有副本记录 {副本ID: 副本信息字典}

        # 1. 构造当前处理的副本文件名 (用于边界索引的键)
        current_filename = f"book-b-{file_num}.json"

        # 初始化用于边界索引的变量
        first_copy_id = None
        last_copy_id = None

        # 2. 遍历该文件中的所有副本记录
        for copy_id, copy_info_dict in copy_records_dict.items():

            status = copy_info_dict.get("status", "未知状态")

            # 状态索引
            if status:
                if status not in book_status_index:
                    book_status_index[status] = []
                # 状态索引记录的是副本 ID
                book_status_index[status].append(copy_id)

            # 边界索引逻辑
            if first_copy_id is None:
                first_copy_id = copy_id

            last_copy_id = copy_id  # 总是更新为当前循环的 ID

        # 3. 生成边界索引
        if first_copy_id and last_copy_id:
            # 提取母本 ID (副本 ID 的前三段)
            start_mother_id = '-'.join(first_copy_id.split('-')[:-1])
            end_mother_id = '-'.join(last_copy_id.split('-')[:-1])

            # 写入边界索引：键是推断出的文件名
            book_copy_boundary_index[current_filename] = [start_mother_id, end_mother_id]

        # 4. 递增文件计数器
        file_num += 1

    # ⭐️ 修正 2：返回时使用修正后的变量名
    return book_name_index, book_class_index, book_status_index, book_zuozhe_index, book_copy_boundary_index


# 将索引数据写入文件
def write_index_to_file(name_, class_, status_, zuozhe_, _sw, name_pach, class_pach, status_pach, zuozhe_pach, sw_pach):
    # 保存书名索引
    with open(name_pach, 'w', encoding='utf-8') as f:
        json.dump(name_, f, ensure_ascii=False, indent=4)

    # 保存状态索引
    with open(status_pach, 'w', encoding='utf-8') as f:
        json.dump(status_, f, ensure_ascii=False, indent=4)

    # 保存作者索引
    with open(zuozhe_pach, 'w', encoding='utf-8') as f:
        json.dump(zuozhe_, f, ensure_ascii=False, indent=4)

    # 保存类别索引
    with open(class_pach, 'w', encoding='utf-8') as f:
        json.dump(class_, f, ensure_ascii=False, indent=4)

    # 保存首尾索引
    with open(sw_pach, 'w', encoding='utf-8') as f:
        json.dump(_sw, f, ensure_ascii=False, indent=4)


def input_oput_index():
    data_pach = book_pach_db_data()
    data_b_pach = book_pach_db_data_b()
    index_pach = book_pach_index()
    index_pach_class = os.path.join(index_pach, "book-class-index.json")
    index_pach_name = os.path.join(index_pach, "book-name-index.json")
    index_pach_status = os.path.join(index_pach, "book-status-index.json")
    index_pach_zuozhe = os.path.join(index_pach, "book-zuozhe-index.json")
    index_pach_sw = os.path.join(index_pach, "book-sw-index.json")

    book_name_index, book_class_index, book_status_index, book_zuozhe_index, book_sw_index = generate_index(
        data_pach, data_b_pach)

    write_index_to_file(book_name_index, book_class_index, book_status_index, book_zuozhe_index, book_sw_index,
                        index_pach_name, index_pach_class, index_pach_status,
                        index_pach_zuozhe, index_pach_sw)
