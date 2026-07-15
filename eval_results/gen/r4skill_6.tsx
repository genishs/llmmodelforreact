import React, { useState } from 'react';

interface PriceProps {
  amount: number;
}

function Price({ amount }: PriceProps) {
  const [qty, setQty] = useState<number>(1);
  const total: number = amount * qty;
  return <div onClick={() => setQty(qty + 1)}>{total}</div>;
}

export default Price;