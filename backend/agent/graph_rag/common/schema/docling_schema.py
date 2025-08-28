# -*- coding: utf-8 -*-


# ====== SCHEMA (chuỗi) ======
DOCLING_SCHEMA = """
Node labels & properties:
- :Quytrinh
  - title: STRING (unique)
- :Phamvi
  - proc: STRING (Quytrinh.title)
  - tableIdx: INTEGER
  - code: STRING (La Mã, vd: "I")
  - title: STRING
  - label: STRING
- :Thutuc
  - proc: STRING
  - tableIdx: INTEGER
  - sectionCode: STRING (La Mã)
  - code: STRING (vd: "1", "2", hoặc "-")
  - title: STRING
  - label: STRING ("Thutuc")
  - level: STRING ("group")
- :Thanhphandutoan
  - name: STRING (unique)
- :Hosochungtu
  - name: STRING (unique)
- :Ghichu
  - key: STRING (unique)
  - text: STRING


Relationships (directed):
(:Quytrinh)-[:HAS_SECTION]->(:Phamvi)
(:Phamvi)-[:HAS_ITEM]->(:Thutuc)
(:Thutuc)-[:REQUIRES {item: <letter>}]->(:Thanhphandutoan)
(:Thutuc)-[:REQUIRES {item: <letter>}]->(:Hosochungtu)
(:Thutuc)-[:NOTE {item: <letter>}]->(:Ghichu)
"""


# ====== PROMPTS (few-shots + template tóm tắt) ======
DOCLING_PROMPTS = {
    "results_template": """Bạn là trợ lý phân tích dữ liệu.
Nhiệm vụ: Tóm tắt kết quả truy vấn Neo4j bằng tiếng Việt, súc tích, dễ hiểu.
Yêu cầu:
- Trả lời trực tiếp câu hỏi.
- Nêu số lượng hàng và vài mục tiêu biểu (tối đa 5).
- Nếu không có kết quả, ghi rõ "Không có kết quả" và gợi ý điều chỉnh truy vấn.
Câu hỏi: {question}
Cypher:
{cypher}


Kết quả (JSON, tối đa 30 dòng):
{results}


Viết câu trả lời:
""",


    # IMPORTANT: ví dụ tối giản, bám chặt schema & mẫu mong muốn
    "few_shot_examples": [
        # 1) HSCT cho Công tác phí trong nước (I, bảng thứ 2) — MẪU BẠN MUỐN
        {
            "question": "Liệt kê Hồ sơ chứng từ cho Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc)\n"
                "MATCH (t)-[:REQUIRES]->(h:Hosochungtu)\n"
                "RETURN DISTINCT h.name AS hoSo"
            ),
        },


        # 2) TPDT cho Công tác phí trong nước (I, bảng thứ 2)
        {
            "question": "Liệt kê Thành phần dự toán cho Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc)\n"
                "MATCH (t)-[:REQUIRES]->(tp:Thanhphandutoan)\n"
                "RETURN DISTINCT tp.name AS thanhPhan"
            ),
        },


        # 3) HSCT cho item 'a' của thủ tục code '1' (I, bảng thứ 2)
        {
            "question": "Hồ sơ chứng từ mục a cho thủ tục code 1 của Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'1'})\n"
                "MATCH (t)-[:REQUIRES {item:'a'}]->(h:Hosochungtu)\n"
                "RETURN DISTINCT h.name AS hoSo"
            ),
        },


        # 4) TPDT cho item 'b' của thủ tục code '2' (I, bảng thứ 2)
        {
            "question": "Thành phần dự toán mục b cho thủ tục code 2 của Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'2'})\n"
                "MATCH (t)-[:REQUIRES {item:'b'}]->(tp:Thanhphandutoan)\n"
                "RETURN DISTINCT tp.name AS thanhPhan"
            ),
        },


        # 5) Ghi chú item 'b' của thủ tục code '2' (I, bảng thứ 2)
        {
            "question": "Ghi chú mục b cho thủ tục code 2 của Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'2'})\n"
                "MATCH (t)-[:NOTE {item:'b'}]->(g:Ghichu)\n"
                "RETURN g.text AS ghiChu"
            ),
        },


        # 6) Liệt kê thủ tục (code, title) thuộc Công tác phí trong nước (I, bảng thứ 2)
        {
            "question": "Liệt kê các Thủ tục thuộc Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc)\n"
                "RETURN t.code AS code, t.title AS title\n"
                "ORDER BY CASE WHEN t.code =~ '\\\\d+' THEN toInteger(t.code) ELSE 999999 END, t.code"
            ),
        },


        # 7) Đếm số Thủ tục trong Công tác phí trong nước (I, bảng thứ 2)
        {
            "question": "Đếm số Thủ tục trong Công tác phí trong nước.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc)\n"
                "RETURN count(t) AS soThuTuc"
            ),
        },


        # 8) Liệt kê thủ tục có code '-' trong Phạm vi 'II' (bảng thứ 2)
        {
            "question": "Liệt kê thủ tục có code '-' trong Phạm vi II.",
            "cypher": (
                "MATCH (:Phamvi {code:'II', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'-'})\n"
                "RETURN t.code AS code, t.title AS title\n"
                "ORDER BY t.title"
            ),
        },


        # 9) Tìm thủ tục có TPDT chứa một cụm từ (ví dụ “Thẻ lên máy bay”)
        {
            "question": "Những thủ tục có Thành phần dự toán chứa cụm 'Thẻ lên máy bay' là gì?",
            "cypher": (
                "MATCH (t:Thutuc)-[:REQUIRES]->(tp:Thanhphandutoan)\n"
                "WHERE tp.name CONTAINS 'Thẻ lên máy bay'\n"
                "RETURN t.sectionCode AS phamVi, t.code AS code, t.title AS title\n"
                "ORDER BY t.sectionCode, CASE WHEN t.code =~ '\\\\d+' THEN toInteger(t.code) ELSE 999999 END, t.code"
            ),
        },


        # 10) Trả về đủ bộ (TPDT/HSCT/Ghi chú) cho một thủ tục & item
        {
            "question": "Cho thủ tục code '2' của Công tác phí trong nước, liệt kê TPDT/HSCT/Ghi chú của item 'b'.",
            "cypher": (
                "MATCH (:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'2'})\n"
                "OPTIONAL MATCH (t)-[:REQUIRES {item:'b'}]->(tp:Thanhphandutoan)\n"
                "OPTIONAL MATCH (t)-[:REQUIRES {item:'b'}]->(hs:Hosochungtu)\n"
                "OPTIONAL MATCH (t)-[:NOTE {item:'b'}]->(g:Ghichu)\n"
                "RETURN t.code AS thuTuc, 'b' AS item, "
                "collect(DISTINCT tp.name) AS thanhPhanDuToan, "
                "collect(DISTINCT hs.name) AS hoSoChungTu, "
                "collect(DISTINCT g.text) AS ghiChu"
            ),
        },
    ]
}



