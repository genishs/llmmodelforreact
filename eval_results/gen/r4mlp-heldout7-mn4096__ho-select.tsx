import React from 'react';

interface EgovSelectProps {
  id: string;
  name: string;
  title?: string;
  options: { label: string; value: string }[];
  setValue: string;
  setter: (v: string) => void;
}

function EgovSelect({ id, name, title = '', options, setValue, setter }: EgovSelectProps) {
  console.log('egovSelect', id, name, title, options, setValue, setter);
  return (
    <select
      id={id}
      name={name}
      title={title}
      defaultValue={setValue}
      onChange={(e) => {
        const v = e.target.value;
        console.log('select Change!! : ', v);
        setter(v);
      }}
    >
      {options.map((option, i) => {
        return (
          <option key={i} value={option.value}>
            {option.label}
          </option>
        );
      })}
    </select>
  );
}

export default EgovSelect;