import React from 'react';

interface FieldProps<T> {
  data: T;
  name: keyof T;
  render?: (value: T[keyof T]) => React.ReactNode;
}

function Field<T extends object>({ data, name, render }: FieldProps<T>) {
  const value = data[name];
  return <span>{render ? render(value) : String(value)}</span>;
}

export default Field;