"""
연습용 데이터 준비 스크립트
React Q&A 형태의 학습 데이터를 생성합니다.

실행: python src/prepare_data.py
"""

import json
import os
from pathlib import Path

# 연습용 React Q&A 샘플 데이터
SAMPLE_DATA = [
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
        "input": "API URL: https://api.example.com/users",
        "output": """import React, { useState, useEffect } from 'react';

function UserList() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await fetch('https://api.example.com/users');
        if (!response.ok) throw new Error('데이터 로드 실패');
        const data = await response.json();
        setUsers(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  if (loading) return <p>로딩 중...</p>;
  if (error) return <p>오류: {error}</p>;

  return (
    <ul>
      {users.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}

export default UserList;"""
    },
    {
        "instruction": "React에서 커스텀 훅을 만드는 방법을 예시 코드로 보여줘",
        "input": "로컬스토리지와 동기화되는 상태 관리 훅",
        "output": """import { useState, useEffect } from 'react';

// 커스텀 훅: localStorage와 동기화
function useLocalStorage(key, initialValue) {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(error);
      return initialValue;
    }
  });

  const setValue = (value) => {
    try {
      const valueToStore = value instanceof Function
        ? value(storedValue)
        : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue];
}

// 사용 예시
function App() {
  const [theme, setTheme] = useLocalStorage('theme', 'light');

  return (
    <div>
      <p>현재 테마: {theme}</p>
      <button onClick={() => setTheme('dark')}>다크 모드</button>
      <button onClick={() => setTheme('light')}>라이트 모드</button>
    </div>
  );
}

export default App;"""
    },
    {
        "instruction": "React Context API로 전역 상태를 관리하는 코드를 작성해줘",
        "input": "사용자 인증 상태 관리",
        "output": """import React, { createContext, useContext, useState } from 'react';

// Context 생성
const AuthContext = createContext(null);

// Provider 컴포넌트
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const login = (userData) => {
    setUser(userData);
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// 커스텀 훅
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

// 사용 예시
function LoginButton() {
  const { user, login, logout } = useAuth();

  if (user) {
    return (
      <div>
        <span>{user.name}님 환영합니다</span>
        <button onClick={logout}>로그아웃</button>
      </div>
    );
  }

  return (
    <button onClick={() => login({ id: 1, name: '홍길동' })}>
      로그인
    </button>
  );
}"""
    },
    {
        "instruction": "React에서 폼 유효성 검사를 구현해줘",
        "input": "이메일, 비밀번호 입력 폼",
        "output": """import React, { useState } from 'react';

function LoginForm() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [errors, setErrors] = useState({});

  const validate = () => {
    const newErrors = {};

    if (!formData.email) {
      newErrors.email = '이메일을 입력하세요';
    } else if (!/\\S+@\\S+\\.\\S+/.test(formData.email)) {
      newErrors.email = '올바른 이메일 형식이 아닙니다';
    }

    if (!formData.password) {
      newErrors.password = '비밀번호를 입력하세요';
    } else if (formData.password.length < 8) {
      newErrors.password = '비밀번호는 8자 이상이어야 합니다';
    }

    return newErrors;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // 실시간 에러 제거
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = validate();

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    console.log('로그인 시도:', formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <input
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          placeholder="이메일"
        />
        {errors.email && <span style={{color: 'red'}}>{errors.email}</span>}
      </div>
      <div>
        <input
          type="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          placeholder="비밀번호"
        />
        {errors.password && <span style={{color: 'red'}}>{errors.password}</span>}
      </div>
      <button type="submit">로그인</button>
    </form>
  );
}

export default LoginForm;"""
    },
]


def format_for_training(item):
    """Alpaca 형식으로 변환"""
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


def prepare_data(output_dir="./data/processed"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 학습/검증 분할 (80/20)
    split_idx = int(len(SAMPLE_DATA) * 0.8)
    train_data = SAMPLE_DATA[:split_idx]
    val_data = SAMPLE_DATA[split_idx:]

    # train 저장
    train_path = os.path.join(output_dir, "react_train.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(format_for_training(item), ensure_ascii=False) + "\n")

    # val 저장
    val_path = os.path.join(output_dir, "react_val.jsonl")
    with open(val_path, "w", encoding="utf-8") as f:
        for item in val_data:
            f.write(json.dumps(format_for_training(item), ensure_ascii=False) + "\n")

    print(f"학습 데이터: {len(train_data)}개 → {train_path}")
    print(f"검증 데이터: {len(val_data)}개 → {val_path}")
    print("\n샘플 확인:")
    print(format_for_training(SAMPLE_DATA[0])["text"][:200] + "...")


if __name__ == "__main__":
    prepare_data()
