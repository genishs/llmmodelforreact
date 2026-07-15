import React, { useState } from 'react';

interface CounterProps {
  initial?: number;
}

function Counter({ initial = 0 }: CounterProps) {
  const [count, setCount] = useState(initial);
  return (
    <div>
      <h1>{count}</h1>
      <button