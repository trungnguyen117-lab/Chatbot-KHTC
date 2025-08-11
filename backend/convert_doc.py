import os
import json
from docling.document_converter import DocumentConverter
import re

# Khởi tạo đối tượng DocumentConverter để chuyển đổi tài liệu
converter = DocumentConverter()

def is_toc_line(text):
    """
    Kiểm tra xem dòng text có phải là dòng mục lục hay không.
    - Mục lục thường có dấu chấm chấm ... hoặc tab, theo sau là số trang.
    - Hoặc là dòng dạng "CHƯƠNG 1", "CHƯƠNG 2.1", ...
    """
    text = text.strip()
    # Kiểm tra mẫu có dạng dấu chấm hoặc tab + số cuối dòng
    if re.search(r'(\.{2,}|\t)?\s*\d+$', text):
        return True
    # Kiểm tra dòng bắt đầu bằng CHƯƠNG và số chương (có thể có phần thập phân)
    if re.match(r'^CHƯƠNG\s+\d+(\.\d+)*$', text, re.IGNORECASE):
        return True
    return False

def convert_doc_to_json(file_path, output_folder):
    """
    Hàm đọc file DOCX, tách nội dung theo từng chương,
    và gắn các bảng dữ liệu vào đúng chương tương ứng.
    Cuối cùng xuất từng chương thành file JSON riêng.
    """
    # Chuyển đổi file DOCX sang đối tượng tài liệu của Docling
    result = converter.convert(file_path)
    # Lấy dữ liệu tài liệu dưới dạng dict để dễ thao tác
    doc_dict = result.document.model_dump()

    elements = []

    # Gán order cho từng đoạn text theo thứ tự xuất hiện
    for idx, t in enumerate(doc_dict.get("texts", [])):
        elements.append({
            "type": "text",
            "text": t.get("text", "").strip(),
            "order": idx,  # Tự gán thứ tự từ 0,1,2,...
            "data": None
        })

    # Gán order cho bảng, tiếp tục tăng order
    start_idx = len(elements)
    for idx, tb in enumerate(doc_dict.get("tables", [])):
        elements.append({
            "type": "table",
            "text": None,
            "order": start_idx + idx,
            "data": tb.get("data", {}).get("grid", [])
        })

    # Sắp xếp theo thứ tự gán (thực ra lúc này elements đã đúng thứ tự rồi)
    elements.sort(key=lambda x: x["order"])


    # Biến lưu danh sách các chương và chương hiện tại đang xử lý
    chapters = []
    current_chapter = None

    # Duyệt qua từng phần tử theo thứ tự
    for el in elements:
        if el["type"] == "text":
            text_content = el["text"]
            # Bỏ qua các dòng trống hoặc dòng là mục lục
            if not text_content or is_toc_line(text_content):
                continue

            # Nếu là tiêu đề chương (bắt đầu bằng chữ "CHƯƠNG")
            if text_content.upper().startswith("CHƯƠNG"):
                # Nếu đã có chương trước, lưu lại chương đó
                if current_chapter:
                    chapters.append(current_chapter)
                # Tạo chương mới với tên chương và danh sách nội dung trống
                current_chapter = {
                    "chapter": re.sub(r'\s+\d+$', '', text_content),  # Loại bỏ số cuối nếu có
                    "content": [],   # Danh sách các đoạn văn bản trong chương
                    "tables": []     # Danh sách bảng trong chương
                }
            else:
                # Nếu không phải tiêu đề chương thì thêm text vào nội dung chương hiện tại
                if current_chapter:
                    current_chapter["content"].append(text_content)

        elif el["type"] == "table":
            # Nếu phần tử là bảng và đang ở trong chương hiện tại
            if current_chapter and el["data"]:
                # Lấy header bảng (dòng đầu tiên)
                header = [cell.get("text", "").strip() for cell in el["data"][0]] if el["data"] else []
                data = []
                # Duyệt từng hàng dữ liệu (bỏ header)
                for row in el["data"][1:]:
                    row_data = {}
                    # Gán dữ liệu từng ô với header tương ứng
                    for i, cell in enumerate(row):
                        key = header[i] if i < len(header) else f"col_{i}"
                        row_data[key] = cell.get("text", "").strip()
                    data.append(row_data)
                # Thêm bảng vào danh sách bảng của chương
                current_chapter["tables"].append({
                    "title": "Bảng dữ liệu",
                    "data": data
                })

    # Thêm chương cuối cùng vào danh sách nếu có
    if current_chapter:
        chapters.append(current_chapter)

    # Tạo thư mục đầu ra nếu chưa có
    # Lấy tên tài liệu từ file_path (không có đuôi)
    doc_name = os.path.splitext(os.path.basename(file_path))[0]

    # Thư mục lưu theo dạng output_folder/<Tên tài liệu>
    doc_output_dir = os.path.join(output_folder, doc_name)
    os.makedirs(doc_output_dir, exist_ok=True)

    # Lưu từng chapter thành file JSON riêng
    for i, chapter in enumerate(chapters, start=1):
        chapter_path = os.path.join(doc_output_dir, f"chapter_{i}.json")
        with open(chapter_path, "w", encoding="utf-8") as f:
            json.dump(chapter, f, ensure_ascii=False, indent=2)

    print(f"✅ [{file_path}] -> {len(chapters)} chương, lưu tại '{doc_output_dir}'")
