# Quản lý package Python với uv

Dự án này sử dụng **uv** để quản lý dependencies Python.

## Cài đặt uv

```bash
pip install uv
```

## Thêm package mới

```bash
uv add <tên-package>
```

## Cài đặt toàn bộ package cho môi trường mới

```bash
uv pip install
```

## Lưu ý
- Không sử dụng pip hoặc poetry để cài/thêm/xóa package.
- Không cần requirements.txt, chỉ cần pyproject.toml và uv.lock.
- Nếu có file requirements.txt, poetry.lock, Pipfile, hãy xóa đi.

## Tham khảo
- https://github.com/astral-sh/uv
