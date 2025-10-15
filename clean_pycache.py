import os
import shutil
   
def delete_pycache(directory):
    """
    Quét và xóa tất cả các thư mục __pycache__ trong một thư mục chỉ định.
    """
    for root, dirs, files in os.walk(directory):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            print(f"Đang xóa: {pycache_path}")
            try:
                shutil.rmtree(pycache_path)
                print("Đã xóa thành công.")
            except OSError as e:
                print(f"Lỗi: {e.strerror}")

if __name__ == "__main__":
    current_directory = os.path.dirname(os.path.abspath(__file__))

    print("Bắt đầu quét và xóa các thư mục __pycache__...")
    delete_pycache(current_directory)
    print("Hoàn tất quá trình dọn dẹp.")