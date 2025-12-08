import json
import os
import re
from .book_modify import book_pach_db_data, book_pach_db_data_b, book_pach_index


def read_json_files_in_directory(directory):
    json_data = []
    # 检查目录是否为空
    if not os.listdir(directory):
        print(f"目录 {directory} 为空，没有文件。")
        return json_data  # 返回空字典
    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        # 判断文件是否是JSON文件
        if filename.endswith(".json"):
            file_path = os.path.join(directory, filename)

            # 尝试打开并加载JSON文件
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    json_data.append(data)
            except json.JSONDecodeError:
                print(f"文件 {filename} 格式错误")
            except PermissionError:
                print(f"没有权限读取文件 {filename}")
    return json_data


def read_json_file(file_path):
    """安全读取单个 JSON 文件并返回内容。"""
    try:
        if not os.path.exists(file_path):
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # 如果读取失败（例如文件损坏），返回空字典
        return {}

MAX_RECORDS = 999
FIXED_CATEGORY_CODE = '1'
DB_PREFIX = "book-"


def find_next_available_book_slot():
    base_dir = book_pach_db_data()
    """
    基于文件连续性原则，查找最大的文件序号，并确定下一个可用的图书槽位。

    :param base_dir: 存放 book-[N].json 文件的基础目录。
    :return: (file_path, next_full_id)
    """
    if not os.path.exists(base_dir):
        # 目录不存在，创建第一个文件 book-1.json
        os.makedirs(base_dir)
        file_path = os.path.join(base_dir, f"{DB_PREFIX}1.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return file_path, f"{FIXED_CATEGORY_CODE}-1-{1:03d}"

    # ----------------------------------------------------
    # 1. 查找最大的文件序号 (N)
    # ----------------------------------------------------
    latest_index = 0
    pattern = re.compile(f"^{DB_PREFIX}(\d+)\.json$")

    for filename in os.listdir(base_dir):
        match = pattern.match(filename)
        if match:
            latest_index = max(latest_index, int(match.group(1)))

    # 如果目录为空，则从 book-1.json 开始
    if latest_index == 0:
        latest_index = 1

    file_path = os.path.join(base_dir, f"{DB_PREFIX}{latest_index}.json")

    # ----------------------------------------------------
    # 2. 检查最大的文件 book-N.json
    # ----------------------------------------------------
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # 文件损坏：基于新的约束，我们仍然需要跳过它，但应该检查下一个文件
        print(f"🚨 警告: 文件 {file_path} 内容损坏。已跳过此文件。")
        # 由于文件连续，损坏的文件视为“已满”，我们检查下一个文件 N+1
        latest_index += 1
        return create_new_book_file(base_dir, latest_index)

    current_count = len(data)

    if current_count < MAX_RECORDS:
        # 文件未满，直接使用
        next_book_num = current_count + 1
        next_id = f"{FIXED_CATEGORY_CODE}-{latest_index}-{next_book_num:03d}"
        return file_path, next_id
    else:
        # 文件已满，创建 book-(N+1).json
        latest_index += 1
        return create_new_book_file(base_dir, latest_index)


# 辅助函数：创建新文件并返回信息
def create_new_book_file(base_dir, file_index):
    new_file_path = os.path.join(base_dir, f"{DB_PREFIX}{file_index}.json")
    with open(new_file_path, 'w', encoding='utf-8') as f:
        json.dump({}, f)
    print(f"创建新文件: {new_file_path}")
    next_id = f"{FIXED_CATEGORY_CODE}-{file_index}-{1:03d}"
    return new_file_path, next_id


DB_PREFIX_B = "book-b-"


def find_next_available_copy_slot():
    base_dir = book_pach_db_data_b()
    """
    基于文件连续性原则，查找最大的副本文件序号，并返回该文件剩余的存储容量。
    """
    if not os.path.exists(base_dir):
        # 目录不存在，创建第一个文件 book-b-1.json
        os.makedirs(base_dir)
        file_path = os.path.join(base_dir, f"{DB_PREFIX_B}1.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return file_path, MAX_RECORDS

    # ----------------------------------------------------
    # 1. 查找最大的文件序号 (N)
    # ----------------------------------------------------
    latest_index = 0
    pattern = re.compile(f"^{DB_PREFIX_B}(\d+)\.json$")

    for filename in os.listdir(base_dir):
        match = pattern.match(filename)
        if match:
            latest_index = max(latest_index, int(match.group(1)))

    if latest_index == 0:
        latest_index = 1

    file_path = os.path.join(base_dir, f"{DB_PREFIX_B}{latest_index}.json")

    # ----------------------------------------------------
    # 2. 检查最大的文件 book-b-N.json
    # ----------------------------------------------------
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # 文件损坏：跳过，并返回下一个新文件 (N+1) 的最大容量
        print(f"🚨 警告: 副本文件 {file_path} 内容损坏。已跳过此文件。")
        latest_index += 1
        return create_new_copy_file(base_dir, latest_index)

    current_count = len(data)

    if current_count < MAX_RECORDS:
        # 文件未满，计算剩余容量并返回
        remaining_slots = MAX_RECORDS - current_count
        return file_path, remaining_slots
    else:
        # 文件已满，创建 book-b-(N+1).json
        latest_index += 1
        return create_new_copy_file(base_dir, latest_index)


# 辅助函数：创建新副本文件并返回信息
def create_new_copy_file(base_dir, file_index):
    new_file_path = os.path.join(base_dir, f"{DB_PREFIX_B}{file_index}.json")
    with open(new_file_path, 'w', encoding='utf-8') as f:
        json.dump({}, f)
    print(f"创建新副本文件: {new_file_path}")
    return new_file_path, MAX_RECORDS


def get_book_record_by_id(book_id):
    """
    根据母本 ID 查找并返回该书的完整信息记录。

    :param book_id: 完整的母本 ID (e.g., '1-3-010')
    :return: 找到的图书记录字典 (e.g., {'name': '...', 'author': '...'}),
             如果未找到或 ID 格式错误，返回 None。
    """
    try:
        # 1. 解析 ID 以确定文件序号
        # ID 格式: FIXED_CATEGORY_CODE - FILE_INDEX - BOOK_NUM
        # 我们需要获取 FILE_INDEX (ID 的第二部分)
        parts = book_id.split('-')
        if len(parts) != 3:
            print(f"警告: 母本 ID 格式错误: {book_id}")
            return None

        file_index = parts[1]  # 例如：'1-3-010' -> '3'

    except Exception:
        print(f"警告: 无法解析 ID {book_id}")
        return None

    # 2. 构造文件路径
    base_dir = book_pach_db_data()  # 获取母本文件目录
    file_path = os.path.join(base_dir, f"book-{file_index}.json")

    # 3. 检查文件是否存在
    if not os.path.exists(file_path):
        # 理论上，如果 ID 是有效的，文件应该存在
        print(f"错误: 找不到 ID {book_id} 对应的文件: {file_path}")
        return None

    # 4. 读取文件并查找指定 ID
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # 查找并返回该 ID 对应的记录
            return data.get(book_id)

    except json.JSONDecodeError:
        print(f"警告: 文件 {file_path} 内容损坏，无法读取。")
        return None
    except Exception as e:
        print(f"读取文件 {file_path} 时发生错误: {e}")
        return None


def find_relevant_copy_files(mother_id):
    """
    使用边界索引，查找所有可能包含目标母本副本的文件名列表。

    :param mother_id: 目标母本 ID (e.g., '1-3-010')
    :return: 包含相关副本的文件名列表 (e.g., ['book-b-2.json', 'book-b-3.json'])
    """
    index_pach = book_pach_index()
    boundary_index_path = os.path.join(index_pach, "book-sw-index.json")

    boundary_index = read_json_file(boundary_index_path)

    if not boundary_index:
        print("警告: 边界索引文件为空或读取失败。")
        return []

    relevant_files = []

    # 按文件名自然排序，确保按顺序读取
    sorted_filenames = sorted(boundary_index.keys())

    # 查找过程：我们寻找母本 ID 位于 [start_mid, end_mid] 范围内的所有文件。

    # 查找起点：找到第一个 start_mid <= mother_id 的文件
    start_found = False

    for filename in sorted_filenames:
        start_mid, end_mid = boundary_index[filename]

        # 1. 确定查找的起始点 (start_mid <= mother_id)
        if not start_found:
            if start_mid <= mother_id:
                start_found = True
            else:
                # 目标母本 ID 小于当前文件起始点，说明它在更早的文件中，
                # 或者它根本不存在（如果这是第一个文件）。
                continue

        # 2. 从起始点开始，判断是否包含目标母本的副本。
        # 只要母本 ID 位于当前文件的 [起始母本 ID, 结束母本 ID] 范围内，就说明该文件包含目标副本。
        if start_mid <= mother_id <= end_mid:
            relevant_files.append(filename)
        elif mother_id < start_mid:
            # 如果 mother_id 小于当前文件的起始母本 ID，说明目标母本的副本已经全部结束。
            # 因为数据是按 mother_id 有序排列的，所以可以提前终止查找。
            break

        # 如果 mother_id > end_mid, 意味着当前母本的副本已经在这个文件结束了，
        # 但我们必须继续检查下一个文件，直到满足 mother_id < start_mid 的条件才能停止。

    return relevant_files


def get_all_copies_by_mother_id_optimized(mother_id):
    """
    根据母本 ID 高效找到其所有副本内容列表（仅返回副本信息）。
    利用边界索引定位文件，并利用 ID 结构直接匹配。

    :param mother_id: 完整的母本 ID (e.g., '1-3-010')
    :return: 包含所有副本信息字典的列表, 格式为 [{...}, {...}]。
    """

    # --- 阶段 1: 定位相关副本文件 ---
    relevant_files = find_relevant_copy_files(mother_id)

    if not relevant_files:
        return []

    # --- 阶段 2: 逐文件读取并提取副本 ---

    all_copy_details = []
    base_copy_dir = book_pach_db_data_b()

    for filename in relevant_files:
        file_path = os.path.join(base_copy_dir, filename)

        # 读取文件内容：{副本ID: 副本信息字典}
        copy_records_dict = read_json_file(file_path)

        if not copy_records_dict:
            continue

        for copy_id, copy_info in copy_records_dict.items():

            # 从副本 ID 提取母本 ID
            current_mother_id = '-'.join(copy_id.split('-')[:-1])

            # 检查是否是目标母本的副本
            if current_mother_id == mother_id:
                # ⭐️ 关键修改：将 copy_id 键/值对添加到副本信息字典中
                # 这样做可以确保 UI 端的表格能够通过 'copy_id' 键获取到值。
                # 使用 .copy() 以免修改原始数据库记录
                copy_detail = copy_info.copy()
                copy_detail['copy_id'] = copy_id

                all_copy_details.append(copy_detail)

            elif current_mother_id > mother_id:
                # 优化：按母本 ID 排序，超出范围即可停止当前文件的查找。
                break

    # --- 阶段 3: 返回结果 ---
    return all_copy_details
