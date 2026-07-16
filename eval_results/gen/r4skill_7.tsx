import React from 'react';

interface PagerProps {
  total: number;
  pageSize: number;
  current: number;
  onChange: (page: number) => void;
}

function Pager({ total, pageSize, current, onChange }: PagerProps) {
  const pageCount: number = Math.ceil(total / pageSize);
  const pages: number[] = [];
  for (let i = 1; i <= pageCount; i++) {
    pages.push(i);
  }
  return (
    <div>
      {pages.map((p) => (
        <button key={p} disabled={p === current} onClick={() => onChange(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}

export default Pager;