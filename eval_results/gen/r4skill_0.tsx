import React from 'react';

interface ListProps<T> {
  items: T[];
  labelKey: keyof T;
}

function List<T extends object>({ items, labelKey }: ListProps<T>) {
  return (
    <ul>
      {items.map((item, index) => (
        <li key={index}>{String(item[labelKey])}</li>
      ))}
    </ul>
  );
}

export default List;