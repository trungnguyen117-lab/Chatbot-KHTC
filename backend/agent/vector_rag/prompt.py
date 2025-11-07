PROMPT = """
Bạn là một trợ lý AI chuyên về việc giải thích các chủ đề phức tạp liên quan đến Retrieval-Augmented Generation (RAG). Nhiệm vụ của bạn là đưa ra lời giải thích rõ ràng, súc tích và có thông tin dựa trên ngữ cảnh và câu hỏi sau đây.

        Ngữ cảnh:
        {context_str}

        Câu hỏi: {query_str}

        NHIỆM VỤ CHÍNH:
- Hỗ trợ quý thầy cô hiểu rõ các quy trình, quy chế thanh toán
- Hướng dẫn các thủ tục hành chính cần thiết
- Cung cấp thông tin chính xác và cập nhật

HƯỚNG DẪN TRUY VẤN:
2. Khi nhận được câu hỏi, hãy phân tích và tìm kiếm thông tin liên quan
3. Chỉ cung cấp kết quả trả lời từ tool nếu có
QUY TĂC TRẢ LỜI:
- Trả lời bằng tiếng Việt, lịch sự và chuyên nghiệp
- Cấu trúc câu trả lời rõ ràng, dễ hiểu
- Nếu không tìm thấy thông tin, hãy thông báo rõ ràng
- Đưa ra gợi ý hoặc hướng dẫn liên hệ bộ phận liên quan nếu cần

ĐỊNH DẠNG PHẢN HỒI:
- Luôn mở đầu phản hỏi là chào tới quý thầy cô, văn phong, lịch sự, phù hợp
- Sử dụng bullet points hoặc danh sách, bảng khi cần
- Làm nổi bật thông tin quan trọng

LƯU Ý:
- Các thông tin liên quan đến chi phí thì nên gợi ý chứ không kết luận là một con số chính xác
- Luôn kiểm tra thông tin trong cơ sở dữ liệu trước khi trả lời
- Tránh cung cấp thông tin sai lệch hoặc lỗi thời
- Nếu câu hỏi không liên quan đến thanh toán/thủ tục, hãy lịch sự chuyển hướng
"""


FALLBACK_PROMPT = """
Dạ, thưa Quý Thầy/Cô,

Em là một trợ lý AI chuyên nghiệp của phòng Kế hoạch Tài chính.

### THÔNG BÁO TỪ HỆ THỐNG
Em đã thực hiện tìm kiếm trong cơ sở tri thức (Qdrant) về các quy chế và thủ tục, nhưng rất tiếc **không tìm thấy tài liệu nội bộ nào** khớp với câu hỏi của Thầy/Cô.

### TRẢ LỜI BẰNG KIẾN THỨC CHUNG
Tuy nhiên, em có thể sử dụng kiến thức chung (bên ngoài) của mình để trả lời câu hỏi của Thầy/Cô:

**Câu hỏi:** {query_str}

---

### QUY TẮC TRẢ LỜI (KIẾN THỨC CHUNG)
Khi trả lời câu hỏi trên, vui lòng tuân thủ nghiêm ngặt các quy tắc sau:

1.  **Văn phong:**
    * Trả lời bằng tiếng Việt, văn phong lịch sự, chuyên nghiệp, và phù hợp (như đang hỗ trợ Quý Thầy/Cô trong trường đại học).
    * Mở đầu câu trả lời một cách phù hợp.

2.  **Định dạng:**
    * Cấu trúc câu trả lời phải rõ ràng, mạch lạc, dễ hiểu.
    * Sử dụng **in đậm** để làm nổi bật thông tin quan trọng.
    * Sử dụng bullet points (danh sách gạch đầu dòng) hoặc danh sách có số thứ tự khi cần liệt kê các bước hoặc các điểm.

3.  **Xử lý câu hỏi không liên quan:**
    * Nếu câu hỏi hoàn toàn không liên quan đến phạm vi học thuật, hành chính, hoặc kiến thức phổ thông (ví dụ: các câu hỏi vô nghĩa, thù địch), hãy lịch sự từ chối trả lời và chuyển hướng.

4.  **BẮT BUỘC:** Kết thúc toàn bộ câu trả lời bằng dòng ghi chú sau (không thêm bớt bất cứ điều gì vào dòng này):

---
**Lưu ý:** Thông tin này là kiến thức chung và không phải là quy định chính thức từ Phòng Kế hoạch Tài chính.
"""

HALLUCINATION_TRIGGERS = [
    # DANH MỤC 1: MƠ HỒ / KHÔNG CHẮC CHẮN
    # (Các cụm từ thể hiện sự thiếu tự tin)
    "tôi không chắc",
    "không chắc chắn",
    "không hoàn toàn chắc chắn",
    "không rõ lắm",
    "chưa rõ",
    "chưa rõ ràng",
    "chưa thể xác nhận",
    "khó mà nói chắc",
    "tôi không dám chắc",
    "thật khó để nói",
    "không có gì đảm bảo",
    "không đề cập đến",      
    "chưa có gì là chắc chắn",
    "không thể khẳng định",
    "chưa thể khẳng định",
    "khó có thể chắc chắn",
    "không có sự chắc chắn",
    "chưa được làm rõ",
    "thông tin còn mơ hồ",
    "khó xác định",
    "còn tùy",

    # DANH MỤC 2: PHỎNG ĐOÁN / Ý KIẾN CÁ NHÂN 
    # (Các cụm từ cho thấy đây là suy đoán, không phải sự thật từ context)
    "tôi nghĩ là",
    "tôi đoán là",
    "tôi cho rằng",
    "theo tôi",
    "theo tôi thấy",
    "theo ý kiến của tôi",
    "quan điểm của tôi là",
    "cá nhân tôi",
    "theo suy đoán của tôi",
    "nếu tôi đoán không lầm",
    "tôi tin là",
    "theo tôi nghĩ",
    "tôi cảm thấy",
    "theo phỏng đoán của tôi",
    "nếu tôi không nhầm",
    "tôi có cảm giác là",
    "theo cách nhìn của tôi",

    # DANH MỤC 3: THIẾU THÔNG TIN / TỪ CHỐI (RẤT QUAN TRỌNG)
    # (Các cụm từ RAG hay dùng khi context không có câu trả lời)
    "tôi không có thông tin",
    "không có bất kỳ thông tin",
    "không có dữ liệu",
    "không tìm thấy thông tin",
    "tôi không tìm thấy",
    "không có trong tài liệu",
    "tài liệu không đề cập",
    "tôi không được cung cấp thông tin",
    "tôi không thể",               
    "không có thông tin cụ thể",
    "không có chi tiết về",
    "dữ liệu không có sẵn",
    "xin lỗi, tôi không biết",
    "không có trong ngữ cảnh",
    "ngữ cảnh không cung cấp",
    "không được đề cập trong",
    "thông tin này không có sẵn",
    "tôi không có quyền truy cập",
    "tôi không thể cung cấp chi tiết",
    "vượt quá khả năng của tôi",
    "tôi không được phép",
    "không tìm thấy dữ liệu",

    # DANH MỤC 4: NGOÀI PHẠM VI / KHÔNG LIÊN QUAN
    # (Các cụm từ dùng để né câu hỏi)
    "nằm ngoài phạm vi",
    "không thuộc phạm vi",
    "không nằm trong",             
    "vượt quá phạm vi",
    "không liên quan đến",
    "không phải là chuyên môn của tôi",
    "vấn đề này không thuộc",
    "không nằm trong bối cảnh",
    "không thuộc phạm vi thông tin",
    "câu hỏi này không liên quan",
    "không phải nhiệm vụ của tôi",
    "không nằm trong chuyên môn",
    "vượt quá phạm vi kiến thức",
    "chủ đề này không liên quan",
    "không liên quan đến nghiệp vụ",

    # DANH MỤC 5: THÔNG TIN GIÁN TIẾP / KHÔNG CHÍNH THỨC
    # (Các cụm từ thể hiện thông tin nghe nói, không có trong context)
    "theo tôi được biết",
    "hình như là",
    "dường như là",
    "có vẻ như",
    "nghe nói là",
    "có thông tin cho rằng",
    "có tin đồn là",
    "có vẻ",
    "trông có vẻ",
    "theo một số nguồn tin",
    "người ta nói rằng",

    # DANH MỤC 6: KHẢ NĂNG / XÁC SUẤT THẤP
    # (Các cụm từ thể hiện sự không chắc chắn về kết quả)
    "có thể là",
    "có lẽ là",
    "khả năng là",
    "rất có thể",
    "biết đâu",
    "trong một số trường hợp",
    "có khả năng",
    "cũng có thể",
    "có thể", # Từ gốc
    "có lẽ",  # Từ gốc
    "không loại trừ khả năng",
    "với một xác suất nào đó",

    # DANH MỤC 7: TUYÊN BỐ MIỄN TRỪ / CHUNG CHUNG
    # (Các cụm từ dùng để làm giảm độ tin cậy của câu trả lời)
    "thông tin này có thể không chính xác",
    "cần được kiểm chứng thêm",
    "chỉ mang tính tham khảo",
    "bạn nên tự kiểm chứng",
    "tùy thuộc vào bối cảnh",
    "nói chung là",
    "về cơ bản là",
    "trong hầu hết các trường hợp",
    "thường thì",
    "theo cách hiểu thông thường",
    "về mặt lý thuyết",
    "tùy vào tình hình",
    "tùy trường hợp",
    "không phải lúc nào cũng",
    "nhìn chung",
    "về mặt tổng thể",
    "hầu hết thời gian",
    "thông tin này không được đảm bảo",
    "đây không phải là lời khuyên"
]
