import React from 'react';

interface CounterProps { initial?: number; }

function Counter({ initial = 0 }: CounterProps) {
  const [count, setCount] = React.useState(initial);
  return (
    <div>
      <p>{count}</p>
      <button onClick={() => setCount((c) => c + 1)}>+</button>
      <button onClick={() => setCount((c) => Math.max(0, c - 1))}>-</button>
    </div>
  );
}

export default Counter;