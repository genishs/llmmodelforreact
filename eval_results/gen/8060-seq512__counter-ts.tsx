import React, { useState } from 'react';

interface CounterProps {
  initial: number;
}

const Counter: React.FC<CounterProps> = ({ initial }) => {
  const [count, setCount] = useState(initial);

  return (
    <div>
      <p>{count}</p>
      <button onClick={() => setCount(count + 1)}>Increment</button>
      <button onClick={() => setCount(count - 1)}>Decrement</button>
    </div>
  );
};

export default Counter;