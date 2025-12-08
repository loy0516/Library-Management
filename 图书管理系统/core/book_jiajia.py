import datetime
import json
import os
from .book_baidu import find_next_available_book_slot, find_next_available_copy_slot, find_relevant_copy_files
from .book_modify import book_pach_db_data, book_pach_db_data_b, book_pach_index


def book_pach():
    current_directory = os.getcwd()
    folder_name = ['db', 'index', 'db/data', 'db/data-b']  # 你可以自定义文件夹的名称
    for folder in folder_name:
        folder_path = os.path.join(current_directory, folder)

        # 检查文件夹是否存在
        if not os.path.exists(folder_path):
            # 如果文件夹不存在，创建文件夹
            os.makedirs(folder_path)
    book__()


def book__():
    # 生成初始文件
    data_pach = book_pach_db_data()
    data_b_pach = book_pach_db_data_b()
    index_pach = book_pach_index()
    index_pach_class = os.path.join(index_pach, "book-class-index.json")
    index_pach_name = os.path.join(index_pach, "book-name-index.json")
    index_pach_status = os.path.join(index_pach, "book-status-index.json")
    index_pach_zuozhe = os.path.join(index_pach, "book-zuozhe-index.json")
    index_pach_sw = os.path.join(index_pach, "book-sw-index.json")
    data_pach_ = os.path.join(data_pach, "book-1.json")
    data_b_pach_ = os.path.join(data_b_pach, "book-b-1.json")
    files_to_create = [
        index_pach_class,
        index_pach_name,
        index_pach_status,
        index_pach_zuozhe,
        index_pach_sw,
        data_pach_,
        data_b_pach_
    ]

    # 遍历并创建文件
    for file_path in files_to_create:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # 写入空字典 {}
                    json.dump({}, f, ensure_ascii=False, indent=4)
                print(f"成功创建空 JSON 文件: {file_path}")
            except Exception as e:
                print(f"创建文件失败 {file_path}: {e}")


def add_db(book_title, author, publisher, isbn, pages, words, category, quantity):
    time_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    """
    添加新的图书母本记录及其所有副本记录。

    :param book_title: 书名
    :param author: 作者
    :param publisher: 出版社
    :param isbn: ISBN
    :param pages: 页数
    :param words: 字数
    :param category: 分类
    :param quantity: 入库数量 (int)
    :return: 成功返回 True，失败返回 False
    """
    try:
        quantity = int(quantity)
        if quantity <= 0:
            print("错误：入库数量必须大于 0。")
            return False
    except ValueError:
        print("错误：入库数量必须是有效数字。")
        return False

    # ----------------------------------------------------
    # 步骤一：处理母本数据 (book-N.json)
    # ----------------------------------------------------

    # 获取下一个可用的母本文件路径和新的母本 ID (e.g., '1-1-001')
    try:
        book_file_path, new_book_id = find_next_available_book_slot()
    except Exception as e:
        print(f"获取母本槽位失败: {e}")
        return False

    # 构造母本记录
    book_record = {
        "name": book_title,
        "author": author,
        "publisher": publisher,
        "isbn": isbn,
        "pages": pages,
        "words": words,
        "category": category,
        "date_added": time_stamp,  # 使用生成的 time_stamp
        # 副本ID列表，初始为空，后面会由副本写入函数更新
        "copies": []
    }

    # 写入母本数据
    try:
        with open(book_file_path, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data[new_book_id] = book_record

            # 写回文件，覆盖原有内容
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
        print(f"✅ 母本记录 {new_book_id} 成功写入文件: {book_file_path}")
    except Exception as e:
        print(f"❌ 母本数据写入失败: {e}")
        # 理论上应该回滚操作，但这里简化处理，直接返回失败
        return False

    # ----------------------------------------------------
    # 步骤二：处理副本数据 (book-b-N.json)
    # ----------------------------------------------------

    # 追踪所有生成的副本ID
    all_copy_ids = []
    # 从 1 开始生成副本编号 (e.g., 1, 2, 3...)
    next_copy_num = 1

    # 循环直到所有副本都被分配和写入
    while quantity > 0:
        # 1. 查找下一个可用副本文件槽位和剩余容量
        try:
            copy_file_path, remaining_slots = find_next_available_copy_slot()
        except Exception as e:
            print(f"获取副本槽位失败: {e}")
            return False

        # 2. 确定本次写入当前文件的副本数量
        copies_to_add_now = min(quantity, remaining_slots)

        # 3. 构造本次要写入的副本记录
        copies_to_write = {}
        for _ in range(copies_to_add_now):
            # 副本 ID 格式: 母本 ID - 副本编号 (e.g., '1-1-001-1')
            copy_id = f"{new_book_id}-{next_copy_num}"
            all_copy_ids.append(copy_id)

            # 默认副本状态为“正常”
            copy_record = {
                "book_id": new_book_id,
                "status": "正常",
                "borrower_name": None,
                "borrow_date": None,
                "due_date": None,
                "notes": None
            }
            copies_to_write[copy_id] = copy_record
            next_copy_num += 1

        # 4. 写入副本数据
        try:
            with open(copy_file_path, 'r+', encoding='utf-8') as f:
                # 注意：这里不能简单使用 json.load(f) 如果文件不存在或为空
                # find_next_available_copy_slot 确保文件是存在的且已初始化为 {}
                data = json.load(f)
                data.update(copies_to_write)

                # 写回文件
                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.truncate()

            print(f"✅ 成功向文件 {copy_file_path} 添加 {copies_to_add_now} 个副本记录。")

        except Exception as e:
            print(f"❌ 副本数据写入失败: {e}")
            return False

        # 5. 更新剩余待处理数量
        quantity -= copies_to_add_now

    # ----------------------------------------------------
    # 步骤三：更新母本记录中的副本列表 (可选，但推荐)
    # ----------------------------------------------------
    # 这一步是确保母本记录中的 "copies" 列表是最新的，便于快速查询该书的所有副本 ID。
    try:
        with open(book_file_path, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            # 更新母本记录中的副本 ID 列表
            data[new_book_id]["copies"] = all_copy_ids

            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
        print(f"✅ 母本记录 {new_book_id} 的副本列表已更新。")
    except Exception as e:
        # 如果更新失败，至少母本和副本数据已经保存，只是母本的 copies 字段不完整
        print(f"⚠️ 警告: 母本副本列表更新失败: {e}")

    return True


def update_mother_field(book_id, key, val):
    """
    更新指定母本 ID (book_id) 的单个字段 (key) 的值 (val)。

    :param book_id: 完整的母本 ID (e.g., '1-3-010')
    :param key: 要修改的字段的英文键名 (e.g., 'author', 'name')
    :param val: 字段的新值
    :return: 成功返回 True，失败返回 False
    """
    try:
        # 1. 🔍 解析 ID 以确定文件路径
        # ID 格式: CATEGORY - FILE_INDEX - BOOK_NUM
        parts = book_id.split('-')
        if len(parts) != 3:
            print(f"ERROR: ID 格式错误: {book_id}")
            return False

        file_index = parts[1]  # 获取文件索引，例如 '3'

        # 构造文件路径 (假设 book_pach_db_data() 返回母本数据目录)
        base_dir = book_pach_db_data()
        file_path = os.path.join(base_dir, f"book-{file_index}.json")

        if not os.path.exists(file_path):
            print(f"ERROR: 找不到 ID {book_id} 对应的文件: {file_path}")
            return False

        # 2. 💾 读取整个文件内容
        # 在读写操作中，必须锁定整个文件以避免并发问题，但在单用户应用中可以简化。
        with open(file_path, 'r+', encoding='utf-8') as f:
            f.seek(0)  # 确保从文件开头开始读取
            data = json.load(f)

            # 3. 🔄 查找记录并更新字段
            if book_id in data:
                # 检查记录中是否有该键，并更新其值
                current_record = data[book_id]

                # 特殊处理：如果修改的是 'quantity' (入库数)，你可能需要重新计算副本索引
                # 但这里我们只进行数据的简单修改
                current_record[key] = val

                # 4. 写入操作：清空文件并写入新数据
                f.seek(0)  # 移动指针到文件开头
                f.truncate()  # 清空文件内容
                json.dump(data, f, ensure_ascii=False, indent=4)

                # ⚠️ 提示：如果修改了书名/作者/分类等字段，你可能还需要在这里更新对应的索引文件！

                return True
            else:
                print(f"ERROR: 文件 {file_path} 中找不到母本 ID {book_id} 的记录。")
                return False

    except json.JSONDecodeError:
        print(f"ERROR: 文件 {file_path} 内容格式错误，无法修改。")
        return False
    except Exception as e:
        print(f"ERROR: 修改母本数据时发生意外错误: {e}")
        return False


def update_copy_field(copy_id, key, val):
    """
    更新指定副本 ID (copy_id) 的单个字段 (key) 的值 (val)。
    使用母本 ID 和边界索引来定位正确的副本数据文件。

    :param copy_id: 完整的副本 ID (e.g., '1-3-010-01')
    :param key: 要修改的字段的英文键名
    :param val: 字段的新值
    :return: 成功返回 True，失败返回 False
    """
    try:
        # 1. 🔍 提取母本 ID
        # 从副本 ID 中提取母本 ID (e.g., '1-3-010-01' -> '1-3-010')
        parts = copy_id.split('-')
        if len(parts) != 4:
            print(f"ERROR: 副本 ID 格式错误: {copy_id}")
            return False

        mother_id = '-'.join(parts[:-1])  # '1-3-010'

        # 2. 📁 利用边界索引定位文件
        # 调用核心函数，找到包含该母本副本的所有文件名
        relevant_files = find_relevant_copy_files(mother_id)

        # 对于修改操作，理论上一个副本 ID 只会存在于一个文件中。
        # 我们只取第一个相关文件。
        if not relevant_files:
            print(f"ERROR: 找不到母本 ID {mother_id} 对应的副本文件记录。")
            return False

        # 构造文件路径
        filename = relevant_files[0]
        base_dir = book_pach_db_data_b()  # 获取副本数据目录
        file_path = os.path.join(base_dir, filename)

        if not os.path.exists(file_path):
            print(f"ERROR: 副本文件不存在: {file_path}")
            return False

        # 3. 💾 读取、修改和写入
        with open(file_path, 'r+', encoding='utf-8') as f:
            f.seek(0)
            data = json.load(f)  # data 格式: {副本ID: 副本信息字典, ...}

            if copy_id in data:
                current_copy_record = data[copy_id]

                # 📢 提示：如果修改的是 'status'，你可能需要在成功保存后更新索引。

                current_copy_record[key] = val

                # 写入操作：清空文件并写入新数据
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=4)

                return True
            else:
                print(f"ERROR: 文件 {file_path} 中找不到副本 ID {copy_id} 的记录。")
                return False

    except json.JSONDecodeError:
        print(f"ERROR: 副本文件 {file_path} 内容格式错误，无法修改。")
        return False
    except Exception as e:
        print(f"ERROR: 修改副本数据时发生意外错误: {e}")
        return False
