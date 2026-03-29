# -*- coding: utf-8 -*-
"""
수집된 데이터를 학습용 JSONL로 병합/정제하는 스크립트

실행: python src/build_dataset.py
"""

import json
import random
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 직접 작성한 고품질 React Q&A (기존 샘플 + 추가)
HANDCRAFTED_QA = [
    {
        "instruction": "React에서 useState를 사용해서 카운터를 만들어줘",
        "input": "",
        "output": """import React, { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>현재 카운트: {count}</p>
      <button onClick={() => setCount(count + 1)}>증가</button>
      <button onClick={() => setCount(count - 1)}>감소</button>
      <button onClick={() => setCount(0)}>초기화</button>
    </div>
  );
}

export default Counter;"""
    },
    {
        "instruction": "useEffect로 API 데이터를 불러오는 컴포넌트를 작성해줘",
        "input": "API URL: /api/users",
        "output": """import React, { useState, useEffect } from 'react';

function UserList() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await fetch('/api/users');
        if (!response.ok) throw new Error('데이터 로드 실패');
        const data = await response.json();
        setUsers(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : '알 수 없는 오류');
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  if (loading) return <div>로딩 중...</div>;
  if (error) return <div>오류: {error}</div>;

  return (
    <ul>
      {users.map((user: any) => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}

export default UserList;"""
    },
    {
        "instruction": "React 커스텀 훅으로 디바운스를 구현해줘",
        "input": "",
        "output": """import { useState, useEffect } from 'react';

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

// 사용 예시
function SearchInput() {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    if (debouncedQuery) {
      console.log('검색:', debouncedQuery);
      // API 호출
    }
  }, [debouncedQuery]);

  return (
    <input
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      placeholder="검색어 입력..."
    />
  );
}

export { useDebounce };"""
    },
    {
        "instruction": "React TypeScript에서 제네릭 컴포넌트를 만들어줘",
        "input": "리스트 아이템을 렌더링하는 제네릭 List 컴포넌트",
        "output": """import React from 'react';

interface ListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  keyExtractor: (item: T) => string;
  emptyMessage?: string;
}

function List<T>({
  items,
  renderItem,
  keyExtractor,
  emptyMessage = '데이터가 없습니다.',
}: ListProps<T>) {
  if (items.length === 0) {
    return <div className="empty">{emptyMessage}</div>;
  }

  return (
    <ul>
      {items.map((item, index) => (
        <li key={keyExtractor(item)}>
          {renderItem(item, index)}
        </li>
      ))}
    </ul>
  );
}

// 사용 예시
interface User {
  id: number;
  name: string;
}

function UserPage() {
  const users: User[] = [
    { id: 1, name: '김철수' },
    { id: 2, name: '이영희' },
  ];

  return (
    <List<User>
      items={users}
      keyExtractor={(u) => String(u.id)}
      renderItem={(user) => <span>{user.name}</span>}
    />
  );
}

export default List;"""
    },
    {
        "instruction": "React에서 무한 스크롤을 구현해줘",
        "input": "",
        "output": """import React, { useState, useEffect, useRef, useCallback } from 'react';

interface Item {
  id: number;
  title: string;
}

function InfiniteScroll() {
  const [items, setItems] = useState<Item[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const lastItemRef = useRef<HTMLDivElement | null>(null);

  const fetchItems = useCallback(async (pageNum: number) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/items?page=${pageNum}&limit=20`);
      const data = await response.json();
      if (data.length < 20) setHasMore(false);
      setItems((prev) => [...prev, ...data]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems(page);
  }, [page, fetchItems]);

  useEffect(() => {
    if (!hasMore) return;

    observerRef.current = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !loading) {
        setPage((prev) => prev + 1);
      }
    });

    if (lastItemRef.current) {
      observerRef.current.observe(lastItemRef.current);
    }

    return () => observerRef.current?.disconnect();
  }, [loading, hasMore]);

  return (
    <div>
      {items.map((item) => (
        <div key={item.id} style={{ padding: 16, borderBottom: '1px solid #eee' }}>
          {item.title}
        </div>
      ))}
      <div ref={lastItemRef} />
      {loading && <div>로딩 중...</div>}
      {!hasMore && <div>모든 데이터를 불러왔습니다.</div>}
    </div>
  );
}

export default InfiniteScroll;"""
    },
    {
        "instruction": "React에서 드래그 앤 드롭 리스트를 구현해줘",
        "input": "",
        "output": """import React, { useState, useRef } from 'react';

interface DragItem {
  id: number;
  content: string;
}

function DragDropList() {
  const [items, setItems] = useState<DragItem[]>([
    { id: 1, content: '항목 1' },
    { id: 2, content: '항목 2' },
    { id: 3, content: '항목 3' },
    { id: 4, content: '항목 4' },
  ]);

  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  const handleDragStart = (index: number) => {
    dragItem.current = index;
  };

  const handleDragEnter = (index: number) => {
    dragOverItem.current = index;
  };

  const handleDrop = () => {
    if (dragItem.current === null || dragOverItem.current === null) return;

    const newItems = [...items];
    const [removed] = newItems.splice(dragItem.current, 1);
    newItems.splice(dragOverItem.current, 0, removed);

    dragItem.current = null;
    dragOverItem.current = null;
    setItems(newItems);
  };

  return (
    <ul style={{ listStyle: 'none', padding: 0 }}>
      {items.map((item, index) => (
        <li
          key={item.id}
          draggable
          onDragStart={() => handleDragStart(index)}
          onDragEnter={() => handleDragEnter(index)}
          onDragEnd={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          style={{
            padding: 12,
            margin: 4,
            background: '#f0f0f0',
            cursor: 'grab',
            borderRadius: 4,
          }}
        >
          {item.content}
        </li>
      ))}
    </ul>
  );
}

export default DragDropList;"""
    },
    {
        "instruction": "React에서 모달 컴포넌트를 Portal로 구현해줘",
        "input": "",
        "output": """import React, { useEffect } from 'react';
import ReactDOM from 'react-dom';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

function Modal({ isOpen, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fff', borderRadius: 8, padding: 24,
          minWidth: 320, maxWidth: '90vw',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ margin: 0 }}>{title}</h2>
            <button onClick={onClose}>×</button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body
  );
}

export default Modal;"""
    },
    {
        "instruction": "React에서 데이터 테이블에 정렬과 페이지네이션을 구현해줘",
        "input": "",
        "output": """import React, { useState, useMemo } from 'react';

interface Column<T> {
  key: keyof T;
  label: string;
  sortable?: boolean;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  pageSize?: number;
}

function DataTable<T extends { id: number }>({
  data,
  columns,
  pageSize = 10,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortKey, sortDir]);

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paginated = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const handleSort = (key: keyof T) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
    setCurrentPage(1);
  };

  return (
    <div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                onClick={() => col.sortable && handleSort(col.key)}
                style={{ cursor: col.sortable ? 'pointer' : 'default', padding: 8, borderBottom: '2px solid #ddd' }}
              >
                {col.label}
                {sortKey === col.key && (sortDir === 'asc' ? ' ▲' : ' ▼')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {paginated.map((row) => (
            <tr key={row.id}>
              {columns.map((col) => (
                <td key={String(col.key)} style={{ padding: 8, borderBottom: '1px solid #eee' }}>
                  {String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button disabled={currentPage === 1} onClick={() => setCurrentPage((p) => p - 1)}>이전</button>
        <span>{currentPage} / {totalPages}</span>
        <button disabled={currentPage === totalPages} onClick={() => setCurrentPage((p) => p + 1)}>다음</button>
      </div>
    </div>
  );
}

export default DataTable;"""
    },
    {
        "instruction": "React에서 토스트 알림 시스템을 구현해줘",
        "input": "",
        "output": """import React, { createContext, useContext, useState, useCallback } from 'react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const COLORS: Record<ToastType, string> = {
  success: '#4caf50',
  error: '#f44336',
  info: '#2196f3',
  warning: '#ff9800',
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  let nextId = 0;

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div style={{ position: 'fixed', bottom: 24, right: 24, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map((toast) => (
          <div
            key={toast.id}
            style={{
              background: COLORS[toast.type],
              color: '#fff',
              padding: '12px 20px',
              borderRadius: 6,
              boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
              animation: 'fadeIn 0.2s ease',
            }}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}"""
    },
    {
        "instruction": "React TypeScript로 로컬스토리지와 동기화되는 상태 관리 훅을 만들어줘",
        "input": "",
        "output": """import { useState, useEffect, Dispatch, SetStateAction } from 'react';

function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(key);
      return stored ? (JSON.parse(stored) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('localStorage write error:', error);
    }
  }, [key, value]);

  return [value, setValue];
}

// 사용 예시
function Settings() {
  const [darkMode, setDarkMode] = useLocalStorage('darkMode', false);
  const [lang, setLang] = useLocalStorage<'ko' | 'en'>('lang', 'ko');

  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={darkMode}
          onChange={(e) => setDarkMode(e.target.checked)}
        />
        다크 모드
      </label>
      <select value={lang} onChange={(e) => setLang(e.target.value as 'ko' | 'en')}>
        <option value="ko">한국어</option>
        <option value="en">English</option>
      </select>
    </div>
  );
}

export { useLocalStorage };"""
    },
]


def format_alpaca(item):
    if item["input"]:
        text = (
            f"### Instruction:\n{item['instruction']}\n\n"
            f"### Input:\n{item['input']}\n\n"
            f"### Response:\n{item['output']}"
        )
    else:
        text = (
            f"### Instruction:\n{item['instruction']}\n\n"
            f"### Response:\n{item['output']}"
        )
    return {"text": text}


def load_github_data(path="./data/raw/github_react_qa.jsonl"):
    items = []
    if not Path(path).exists():
        return items
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def quality_filter(item):
    """Q&A 품질 필터링"""
    output = item.get("output", "")
    instruction = item.get("instruction", "")

    if len(output) < 100:
        return False
    if len(instruction) < 10:
        return False
    # React 코드인지 확인
    if "import" not in output and "function" not in output and "const" not in output:
        return False
    return True


def build_dataset(output_dir="./data/processed"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("데이터셋 구축 시작")
    print("=" * 50)

    # 1. 직접 작성 데이터
    handcrafted = [item for item in HANDCRAFTED_QA if quality_filter(item)]
    print(f"직접 작성 Q&A: {len(handcrafted)}개")

    # 2. GitHub 수집 데이터 (있는 경우)
    github_data = load_github_data()
    github_filtered = [item for item in github_data if quality_filter(item)]
    print(f"GitHub 수집 Q&A: {len(github_filtered)}개 (전체 {len(github_data)}개 중 필터 통과)")

    # 3. 병합
    all_data = handcrafted + github_filtered

    # 4. 셔플
    random.seed(42)
    random.shuffle(all_data)

    # 5. 학습/검증 분할 (90/10)
    split = max(1, int(len(all_data) * 0.9))
    train_data = all_data[:split]
    val_data = all_data[split:]

    if not val_data:
        val_data = all_data[-1:]
        train_data = all_data[:-1]

    # 6. Alpaca 포맷으로 저장
    train_path = f"{output_dir}/react_train.jsonl"
    val_path = f"{output_dir}/react_val.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(format_alpaca(item), ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for item in val_data:
            f.write(json.dumps(format_alpaca(item), ensure_ascii=False) + "\n")

    print(f"\n학습 데이터: {len(train_data)}개 -> {train_path}")
    print(f"검증 데이터: {len(val_data)}개 -> {val_path}")
    print("=" * 50)
    print("데이터셋 구축 완료")


if __name__ == "__main__":
    build_dataset()
