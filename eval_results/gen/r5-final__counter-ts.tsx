import React from 'react';

interface CounterProps {
  initial?: number;
}

function Counter({ initial = 0 }: CounterProps): JSX.Element {
  const [count, setCount] = React.useState<number>(initial);

  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount((c) => c + 1)}>Increment</button>
      <button onClick={() => setCount((c) => Math.max(0, c - 1))}>Decrement</button>
    </div>
  );
}

export default Counter;