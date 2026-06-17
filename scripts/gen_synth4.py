# -*- coding: utf-8 -*-
"""
synth4 데이터 생성 — '다른 분포'에 집중(메모리 교훈: 동일스타일 합성은 수익 소진).
약점/벤치 정조준: JS→TS 실변환(B4/B5), 코드리뷰·버그수정(B6), TS 제네릭(B2),
복잡 실무 컴포넌트. 모든 output은 깔끔히 끝맺음(### 누수 방지).

실행: python scripts/gen_synth4.py  → data/handcrafted_synth4.jsonl
"""
import json
from pathlib import Path

EX = []  # (instruction, input, output)

def add(instr, inp, out):
    EX.append({"instruction": instr, "input": inp, "output": out})

# ---------- JS→TS 변환 (B4/B5 분포) ----------
add("이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘.",
"""function UserCard({ user, onSelect }) {
  return (
    <div className="card" onClick={() => onSelect(user.id)}>
      <img src={user.avatar} alt={user.name} />
      <h3>{user.name}</h3>
      <p>{user.email}</p>
    </div>
  );
}

export default UserCard;""",
"""interface User {
  id: number;
  name: string;
  email: string;
  avatar: string;
}

interface UserCardProps {
  user: User;
  onSelect: (id: number) => void;
}

function UserCard({ user, onSelect }: UserCardProps) {
  return (
    <div className="card" onClick={() => onSelect(user.id)}>
      <img src={user.avatar} alt={user.name} />
      <h3>{user.name}</h3>
      <p>{user.email}</p>
    </div>
  );
}

export default UserCard;""")

add("이 커스텀 훅을 TypeScript로 변환하고 반환 타입을 명시해줘.",
"""function useCounter(initial = 0) {
  const [count, setCount] = useState(initial);
  const increment = () => setCount((c) => c + 1);
  const decrement = () => setCount((c) => c - 1);
  const reset = () => setCount(initial);
  return { count, increment, decrement, reset };
}""",
"""import { useState } from 'react';

interface UseCounterReturn {
  count: number;
  increment: () => void;
  decrement: () => void;
  reset: () => void;
}

function useCounter(initial: number = 0): UseCounterReturn {
  const [count, setCount] = useState<number>(initial);
  const increment = () => setCount((c) => c + 1);
  const decrement = () => setCount((c) => c - 1);
  const reset = () => setCount(initial);
  return { count, increment, decrement, reset };
}

export default useCounter;""")

add("이 컴포넌트를 TypeScript로 변환해줘. 이벤트 핸들러 타입도 정확히 지정해줘.",
"""function SearchBox({ value, onChange, onSubmit }) {
  return (
    <form onSubmit={onSubmit}>
      <input value={value} onChange={(e) => onChange(e.target.value)} />
      <button type="submit">검색</button>
    </form>
  );
}""",
"""import React from 'react';

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
}

function SearchBox({ value, onChange, onSubmit }: SearchBoxProps) {
  return (
    <form onSubmit={onSubmit}>
      <input
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      <button type="submit">검색</button>
    </form>
  );
}

export default SearchBox;""")

add("이 리스트 컴포넌트를 TypeScript 제네릭으로 변환해줘. 어떤 아이템 타입이든 받게.",
"""function List({ items, renderItem }) {
  return (
    <ul>
      {items.map((item, i) => (
        <li key={i}>{renderItem(item)}</li>
      ))}
    </ul>
  );
}""",
"""import React from 'react';

interface ListProps<T> {
  items: T[];
  renderItem: (item: T) => React.ReactNode;
}

function List<T>({ items, renderItem }: ListProps<T>) {
  return (
    <ul>
      {items.map((item, i) => (
        <li key={i}>{renderItem(item)}</li>
      ))}
    </ul>
  );
}

export default List;""")

# ---------- 코드리뷰 / 버그수정 (B6 분포) ----------
add("이 코드의 버그를 찾아 수정하고 이유를 설명해줘.",
"""function Timer() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setCount(count + 1), 1000);
  }, []);
  return <div>{count}</div>;
}""",
"""버그가 두 가지 있습니다.

1. **stale closure**: `setCount(count + 1)`이 최초 렌더의 `count`(0)를 캡처해 항상 0+1=1만 됩니다.
2. **인터벌 정리 누락**: `clearInterval`이 없어 언마운트 후에도 타이머가 남아 메모리 누수가 됩니다.

수정:

```tsx
import { useState, useEffect } from 'react';

function Timer() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setCount((c) => c + 1); // 함수형 업데이트로 최신 값 사용
    }, 1000);
    return () => clearInterval(id); // 정리 함수로 인터벌 해제
  }, []);

  return <div>{count}</div>;
}

export default Timer;
```""")

add("이 코드의 문제점을 리뷰하고 개선해줘.",
"""function UserList({ users }) {
  return (
    <div>
      {users.map((user) => (
        <div>{user.name}</div>
      ))}
    </div>
  );
}""",
"""문제점: 리스트 항목에 **key prop이 없습니다.** React가 항목을 식별하지 못해 리렌더 시
비효율적이고, 순서 변경·삭제 시 상태가 어긋날 수 있습니다(콘솔 경고도 발생).

개선:

```jsx
function UserList({ users }) {
  return (
    <div>
      {users.map((user) => (
        <div key={user.id}>{user.name}</div>
      ))}
    </div>
  );
}

export default UserList;
```

`index`를 key로 쓰는 것은 항목이 추가/삭제/정렬되는 리스트에서는 피하고, 고유 `id`를 쓰세요.""")

add("이 useEffect의 의존성 문제를 찾아 고쳐줘.",
"""function Profile({ userId }) {
  const [user, setUser] = useState(null);
  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then((r) => r.json())
      .then(setUser);
  }, []);
  return <div>{user?.name}</div>;
}""",
"""문제: 의존성 배열이 `[]`라서 `userId`가 바뀌어도 다시 패칭하지 않습니다. 첫 `userId`로만
한 번 패칭됩니다.

수정 — `userId`를 의존성에 넣고, 경쟁 상태(race condition)도 방지:

```tsx
import { useState, useEffect } from 'react';

interface User { id: number; name: string; }

function Profile({ userId }: { userId: number }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`/api/users/${userId}`)
      .then((r) => r.json())
      .then((data) => { if (active) setUser(data); });
    return () => { active = false; };
  }, [userId]);

  return <div>{user?.name}</div>;
}

export default Profile;
```""")

# ---------- TS 제네릭 / 실무 훅 (B2 분포) ----------
add("로컬스토리지와 동기화되는 useLocalStorage 훅을 TypeScript 제네릭으로 만들어줘.", "",
"""import { useState, useEffect } from 'react';

function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [stored, setStored] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(stored));
    } catch {
      /* 저장 실패 무시 */
    }
  }, [key, stored]);

  return [stored, setStored];
}

export default useLocalStorage;""")

add("이전 값을 기억하는 usePrevious 훅을 TypeScript 제네릭으로 작성해줘.", "",
"""import { useRef, useEffect } from 'react';

function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref.current;
}

export default usePrevious;""")

add("비동기 함수의 상태(로딩/에러/데이터)를 관리하는 useAsync 훅을 TypeScript 제네릭으로 만들어줘.", "",
"""import { useState, useCallback } from 'react';

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

function useAsync<T>(asyncFn: () => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const run = useCallback(async () => {
    setState({ data: null, loading: true, error: null });
    try {
      const data = await asyncFn();
      setState({ data, loading: false, error: null });
    } catch (e) {
      setState({ data: null, loading: false, error: e as Error });
    }
  }, [asyncFn]);

  return { ...state, run };
}

export default useAsync;""")

# ---------- 복잡 실무 컴포넌트 ----------
add("제어 컴포넌트로 동작하는 재사용 가능한 Modal 컴포넌트를 TypeScript로 만들어줘. ESC로 닫히게.", "",
"""import React, { useEffect } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

function Modal({ isOpen, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {title && <h2>{title}</h2>}
        {children}
        <button onClick={onClose}>닫기</button>
      </div>
    </div>
  );
}

export default Modal;""")

add("정렬 가능한 테이블 컴포넌트를 TypeScript 제네릭으로 만들어줘. 컬럼 정의를 props로 받게.", "",
"""import React, { useState, useMemo } from 'react';

interface Column<T> {
  key: keyof T;
  header: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
}

function DataTable<T extends { id: number | string }>({ columns, rows }: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null);
  const [asc, setAsc] = useState(true);

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === bv) return 0;
      return (av > bv ? 1 : -1) * (asc ? 1 : -1);
    });
  }, [rows, sortKey, asc]);

  const toggleSort = (key: keyof T) => {
    if (sortKey === key) setAsc((p) => !p);
    else { setSortKey(key); setAsc(true); }
  };

  return (
    <table>
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={String(col.key)} onClick={() => toggleSort(col.key)}>
              {col.header}{sortKey === col.key ? (asc ? ' ▲' : ' ▼') : ''}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr key={row.id}>
            {columns.map((col) => (
              <td key={String(col.key)}>{String(row[col.key])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default DataTable;""")

add("폼 입력을 관리하는 useForm 훅을 TypeScript 제네릭으로 만들어줘. 값과 변경 핸들러를 제공해줘.", "",
"""import { useState, ChangeEvent } from 'react';

function useForm<T extends Record<string, string>>(initial: T) {
  const [values, setValues] = useState<T>(initial);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const reset = () => setValues(initial);

  return { values, handleChange, reset, setValues };
}

export default useForm;""")

add("debounce된 검색 입력을 처리하는 SearchInput 컴포넌트를 TypeScript로 만들어줘. 입력 후 300ms 뒤 onSearch 호출.", "",
"""import React, { useState, useEffect } from 'react';

interface SearchInputProps {
  onSearch: (query: string) => void;
  placeholder?: string;
}

function SearchInput({ onSearch, placeholder = '검색...' }: SearchInputProps) {
  const [value, setValue] = useState('');

  useEffect(() => {
    const id = setTimeout(() => onSearch(value), 300);
    return () => clearTimeout(id);
  }, [value, onSearch]);

  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => setValue(e.target.value)}
    />
  );
}

export default SearchInput;""")

add("교차 관찰자(IntersectionObserver)로 무한 스크롤 트리거를 만드는 useInfiniteScroll 훅을 TypeScript로 작성해줘.", "",
"""import { useEffect, useRef } from 'react';

function useInfiniteScroll(onLoadMore: () => void, enabled: boolean = true) {
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) onLoadMore();
      },
      { threshold: 1.0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [onLoadMore, enabled]);

  return sentinelRef;
}

export default useInfiniteScroll;""")

add("이 JS 유틸 컴포넌트를 TypeScript로 변환해줘. 조건부 렌더링 부분의 타입을 명확히.",
"""function Badge({ status, count }) {
  if (count === 0) return null;
  const color = status === 'error' ? 'red' : status === 'warn' ? 'orange' : 'green';
  return <span style={{ background: color }}>{count}</span>;
}""",
"""import React from 'react';

type BadgeStatus = 'error' | 'warn' | 'success';

interface BadgeProps {
  status: BadgeStatus;
  count: number;
}

function Badge({ status, count }: BadgeProps) {
  if (count === 0) return null;
  const color =
    status === 'error' ? 'red' : status === 'warn' ? 'orange' : 'green';
  return <span style={{ background: color }}>{count}</span>;
}

export default Badge;""")

add("이 코드의 성능 문제를 찾아 useMemo/useCallback로 개선해줘.",
"""function ProductList({ products, filter }) {
  const visible = products.filter((p) => p.category === filter);
  const handleClick = (id) => console.log('clicked', id);
  return visible.map((p) => <Item key={p.id} product={p} onClick={handleClick} />);
}""",
"""문제: 매 렌더마다 `filter()`가 전체 배열을 재계산하고, `handleClick`이 새 참조로 생성돼
`Item`이 memo여도 항상 리렌더됩니다.

개선:

```tsx
import { useMemo, useCallback } from 'react';

function ProductList({ products, filter }: ProductListProps) {
  const visible = useMemo(
    () => products.filter((p) => p.category === filter),
    [products, filter]
  );

  const handleClick = useCallback((id: number) => {
    console.log('clicked', id);
  }, []);

  return (
    <>
      {visible.map((p) => (
        <Item key={p.id} product={p} onClick={handleClick} />
      ))}
    </>
  );
}

export default ProductList;
```

`visible`는 입력이 바뀔 때만 재계산되고, `handleClick`은 참조가 안정돼 `Item`의 memo가 동작합니다.""")

add("토글 가능한 아코디언 컴포넌트를 TypeScript로 만들어줘. 여러 항목 중 하나만 열리게.", "",
"""import React, { useState } from 'react';

interface AccordionItem {
  id: string;
  title: string;
  content: React.ReactNode;
}

interface AccordionProps {
  items: AccordionItem[];
}

function Accordion({ items }: AccordionProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  const toggle = (id: string) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="accordion">
      {items.map((item) => (
        <div key={item.id} className="accordion-item">
          <button onClick={() => toggle(item.id)}>{item.title}</button>
          {openId === item.id && <div className="panel">{item.content}</div>}
        </div>
      ))}
    </div>
  );
}

export default Accordion;""")

add("이 클래스 컴포넌트를 함수형 + TypeScript로 변환해줘.",
"""class Toggle extends React.Component {
  state = { on: false };
  handleClick = () => this.setState({ on: !this.state.on });
  render() {
    return <button onClick={this.handleClick}>{this.state.on ? 'ON' : 'OFF'}</button>;
  }
}""",
"""import React, { useState } from 'react';

function Toggle() {
  const [on, setOn] = useState<boolean>(false);
  const handleClick = () => setOn((prev) => !prev);
  return <button onClick={handleClick}>{on ? 'ON' : 'OFF'}</button>;
}

export default Toggle;""")

add("키보드 단축키를 등록하는 useHotkey 훅을 TypeScript로 만들어줘.", "",
"""import { useEffect } from 'react';

function useHotkey(key: string, callback: () => void, ctrl: boolean = false) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === key.toLowerCase() && (!ctrl || e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        callback();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [key, callback, ctrl]);
}

export default useHotkey;""")

# ---------- 기록 ----------
out_path = Path(__file__).resolve().parent.parent / "data" / "handcrafted_synth4.jsonl"
with out_path.open("w", encoding="utf-8") as f:
    for ex in EX:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
print(f"생성: {out_path}  ({len(EX)}개)")
# 분포 요약
js2ts = sum(1 for e in EX if "변환" in e["instruction"])
review = sum(1 for e in EX if "버그" in e["instruction"] or "리뷰" in e["instruction"] or "성능" in e["instruction"] or "문제" in e["instruction"])
print(f"  JS→TS/변환: {js2ts} · 리뷰/버그/성능: {review} · 신규훅/컴포넌트: {len(EX)-js2ts-review}")
