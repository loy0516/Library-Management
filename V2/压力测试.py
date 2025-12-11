import random
import time
from faker import Faker
from datetime import datetime, timedelta
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from natsort import natsort_keygen

# --- 配置参数 ---
NUM_BOOKS = 1000000  # 想要生成的图书母记录数量
MAX_RECORDS_PER_FILE = 999  # 每个 JSON 文件最大记录数
NUM_THREADS = 16  # 使用的线程数量

# !!! 你的自定义路径 (使用原始字符串 r"..." 保持不变) !!!
MOTHER_DATA_DIR = r"E:\pyide_only\学习\图书管理系统\db\data"
COPY_DATA_DIR = r"E:\pyide_only\学习\图书管理系统\db\data-b"

# 随机数据配置 (保持不变)
CATEGORIES = ["小说", "科技", "历史", "传记", "艺术", "教育", "计算机"]
STATUSES = ["正常", "正常", "正常", "借出", "借出", "借出", "丢失", "损坏"]
PUBLISHERS = ["人民邮电出版社", "电子工业出版社", "机械工业出版社", "清华大学出版社", "测试出版社"]
MIN_QUANTITY = 1
MAX_QUANTITY = 5

# --- 全局同步机制 ---
global_copy_count = 0

# 为母本文件写入创建一个全局锁，确保同一时间只有一个线程在进行母本 I/O
mother_file_io_lock = threading.Lock()


# --- 辅助函数 (保持不变) ---

def generate_random_isbn():
    group_prefix = "978-7"
    publisher_code = f"{random.randint(10000, 99999):05d}"
    title_code = f"{random.randint(10, 99):02d}"
    check_digit = random.randint(0, 9)
    return f"{group_prefix}-{publisher_code}-{title_code}-{check_digit}"


def generate_random_datetime(faker_instance, start_days_ago=365):
    """函数接受一个 Faker 实例"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=start_days_ago)
    random_date = faker_instance.date_time_between(start_date=start_date, end_date=end_date)
    return random_date.strftime("%Y-%m-%d %H:%M:%S")


# --- 文件加载和保存 (已优化 _save_data) ---

def _load_data(directory, filename):
    """安全地加载 JSON 文件"""
    file_path = os.path.join(directory, filename)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if content else {}
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


def _save_data(directory, filename, data):
    """安全地保存 JSON 文件，移除内部锁逻辑，由调用方负责加锁"""
    file_path = os.path.join(directory, filename)
    try:
        # 注意：这里没有锁操作，由调用方负责加锁
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"写入文件 {filename} 失败: {e}")


# --- 核心数据生成函数 (保持不变) ---

def generate_single_book_record(mother_id, fake_instance):
    """生成单个图书母记录及其所有副本数据的字典"""

    # 使用线程隔离的 fake_instance 替代全局 fake
    title = fake_instance.catch_phrase() + " - " + fake_instance.last_name() + "传"
    quantity = random.randint(MIN_QUANTITY, MAX_QUANTITY)
    date_added = generate_random_datetime(fake_instance)

    book_record = {
        "mother_id": mother_id,
        "name": title,
        "author": fake_instance.name(),
        "publisher": random.choice(PUBLISHERS),
        "isbn": generate_random_isbn(),
        "pages": str(random.randint(100, 800)),
        "words": str(random.randint(5, 100)) + "万字",
        "category": random.choice(CATEGORIES),
        "date_added": date_added,
        "copies_list": []
    }

    for i in range(1, quantity + 1):
        copy_id = f"{mother_id}-{i}"
        status = random.choice(STATUSES)

        borrower_name = None
        borrow_date = None
        due_date = None
        notes = None

        if status == "借出":
            borrower_name = fake_instance.name()
            start_date_obj = datetime.strptime(date_added, "%Y-%m-%d %H:%M:%S")
            borrow_date_obj = fake_instance.date_time_between(start_date=start_date_obj, end_date=datetime.now())

            borrow_date = borrow_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            due_date_obj = borrow_date_obj + timedelta(days=random.randint(7, 30))
            due_date = due_date_obj.strftime("%Y-%m-%d %H:%M:%S")
            notes = fake_instance.sentence(nb_words=3) if random.random() < 0.2 else None

        copy_record = {
            "copy_id": copy_id,
            "book_id": mother_id,
            "status": status,
            "borrower_name": borrower_name,
            "borrow_date": borrow_date,
            "due_date": due_date,
            "notes": notes
        }

        book_record["copies_list"].append(copy_record)

    return book_record


# --- 线程任务执行函数 (修复母本并发写入问题) ---

def generate_and_save_task(mother_index_start, mother_index_end):
    """
    负责生成并安全保存指定范围内的母本数据，并返回副本数据列表。
    """
    thread_name = threading.current_thread().name
    print(f"{thread_name}: 任务范围 {mother_index_start} 到 {mother_index_end}")

    local_fake = Faker('zh_CN')

    thread_copy_records_list = []
    mother_file_buffer = {}

    for i in range(mother_index_start, mother_index_end):

        # 1. 预计算 ID 和文件名
        mother_count_in_file = (i - 1) % MAX_RECORDS_PER_FILE + 1
        mother_file_index = (i - 1) // MAX_RECORDS_PER_FILE + 1
        mother_id = f"1-{mother_file_index}-{mother_count_in_file:03d}"
        mother_filename = f"book-{mother_file_index}.json"

        # 2. 生成数据
        book_data = generate_single_book_record(mother_id, local_fake)

        # 3. 准备母本数据格式
        mother_record = {
            "name": book_data["name"],
            "author": book_data["author"],
            "publisher": book_data["publisher"],
            "isbn": book_data["isbn"],
            "pages": book_data["pages"],
            "words": book_data["words"],
            "category": book_data["category"],
            "date_added": book_data["date_added"],
            "copies": [copy["copy_id"] for copy in book_data["copies_list"]]
        }

        # 4. 存入母本缓存
        if mother_filename not in mother_file_buffer:
            mother_file_buffer[mother_filename] = {}
        mother_file_buffer[mother_filename][mother_id] = mother_record

        # 5. 暂存副本数据
        thread_copy_records_list.extend(book_data["copies_list"])

        if i % 10000 == 0:
            print(f"{thread_name}: 已生成 {i - mother_index_start + 1} 条数据...")

    # --- 线程 I/O 阶段 (关键修复区域) ---

    # 写入母本文件：每个线程独立负责写入
    for filename, records in mother_file_buffer.items():

        # 🚨 关键修复：加锁，将读取、合并、写入变成原子操作
        mother_file_io_lock.acquire()

        try:
            # 1. 在锁内安全地读取文件
            existing_data = _load_data(MOTHER_DATA_DIR, filename)

            # 2. 在锁内安全地合并数据
            existing_data.update(records)

            # 3. 🆕 新增：写入前对数据进行排序 (保证文件内部记录有序)
            sorted_keys = sorted(existing_data.keys())
            sorted_existing_data = {k: existing_data[k] for k in sorted_keys}

            # 4. 在锁内安全地写入数据
            _save_data(MOTHER_DATA_DIR, filename, sorted_existing_data)

        except Exception as e:
            print(f"线程 {thread_name} 写入文件 {filename} 失败: {e}")
        finally:
            mother_file_io_lock.release()  # 确保释放锁

    print(f"{thread_name}: 母本写入完成。")

    # 返回线程生成的副本记录列表
    return thread_copy_records_list


# --- 主执行函数 (集中排序与顺序写入副本) ---

def run_multithreaded_generation():
    """设置目录并分配多线程任务，并在主线程中集中排序写入副本。"""
    print(f"--- 准备生成 {NUM_BOOKS} 条母本记录 ({NUM_THREADS} 线程) ---")

    # 1. 创建目录
    os.makedirs(MOTHER_DATA_DIR, exist_ok=True)
    os.makedirs(COPY_DATA_DIR, exist_ok=True)

    # 2. 分配任务和收集数据
    futures = []
    chunk_size = NUM_BOOKS // NUM_THREADS
    all_copies_list = []  # 收集所有线程的副本数据

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        for i in range(NUM_THREADS):
            start = i * chunk_size + 1
            end = (i + 1) * chunk_size + 1 if i < NUM_THREADS - 1 else NUM_BOOKS + 1

            future = executor.submit(generate_and_save_task, start, end)
            futures.append(future)

        # 收集所有线程返回的副本数据
        for future in futures:
            thread_copies = future.result()
            all_copies_list.extend(thread_copies)

    # 3. 集中排序副本数据
    print("\n--- 正在排序所有副本数据... ---")
    # 🆕 关键修改：使用 natsort_keygen() 作为 key
    # natsort_keygen() 创建了一个函数，它能将字符串分割成数字和文本段进行数值比较。
    nat_key = natsort_keygen()
    all_copies_list.sort(key=lambda x: nat_key(x['copy_id']))

    print("--- 排序完成，开始顺序写入副本文件... ---")

    # 4. 顺序写入副本文件
    total_copies = len(all_copies_list)

    current_file_index = 1
    current_records = {}  # 当前文件的数据缓存

    for i, copy_record in enumerate(all_copies_list):
        copy_id = copy_record['copy_id']

        # 准备写入 JSON 的格式
        record_to_save = {
            "book_id": copy_record["book_id"],
            "status": copy_record["status"],
            "borrower_name": copy_record.get("borrower_name"),
            "borrow_date": copy_record.get("borrow_date"),
            "due_date": copy_record.get("due_date"),
            "notes": copy_record.get("notes")
        }
        current_records[copy_id] = record_to_save

        # 检查是否达到文件上限
        if (i + 1) % MAX_RECORDS_PER_FILE == 0:
            filename = f"book-b-{current_file_index}.json"
            # 副本写入是主线程顺序执行，无需加锁
            _save_data(COPY_DATA_DIR, filename, current_records)
            print(f"✅ 写入副本文件: {filename}")

            # 重置缓存和文件索引
            current_records = {}
            current_file_index += 1

    # 5. 写入最后一个文件 (如果还有剩余数据)
    if current_records:
        filename = f"book-b-{current_file_index}.json"
        _save_data(COPY_DATA_DIR, filename, current_records)
        print(f"✅ 写入副本文件: {filename} (剩余)")

    # 6. 统计结果
    global global_copy_count
    global_copy_count = total_copies

    total_copy_files = current_file_index if total_copies > 0 else 0

    print("\n==============================================")
    print("✅ 全部数据生成和保存完毕！")
    print(f"总母本记录数: {NUM_BOOKS}")
    print(f"总副本记录数: {total_copies}")
    print(f"母本文件数量: {(NUM_BOOKS - 1) // MAX_RECORDS_PER_FILE + 1} 个 (保存在 {MOTHER_DATA_DIR})")
    print(f"副本文件数量: {total_copy_files} 个 (保存在 {COPY_DATA_DIR})")
    print("==============================================")


# --- 执行脚本 ---
if __name__ == "__main__":
    start_time = time.time()
    run_multithreaded_generation()
    end_time = time.time()
    print(f"总耗时: {end_time - start_time:.2f} 秒")