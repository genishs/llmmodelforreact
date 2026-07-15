import React from 'react';

interface SelectProps<T> {
  options: T[];
  getValue: (option: T) => string | number;
  getLabel: (option: T) => string;
}

function Select<T extends object>({ options, getValue, getLabel }: SelectProps<T>) {
  return (
    <select>
      {options.map((option) => (
        <option key={String(getValue(option))} value={getValue(option)}>
          {getLabel(option)}
        </option>
      ))}
    </select>
  );
}

export default Select;