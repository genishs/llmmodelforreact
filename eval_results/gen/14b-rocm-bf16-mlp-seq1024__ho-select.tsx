import React from 'react';

interface Option {
  label: string;
  value: string;
}

interface Props {
  id: string;
  name: string;
  title: string;
  options: Option[];
  setValue: string;
  setter: (value: string) => void;
}

function EgovSelect({ id, name, title, options, setValue, setter }: Props) {
  console.log("egovSelect", id, name, title, options, setValue, setter);
  return (
    <select
      id={id}
      name={name}
      title={title}
      defaultValue={setValue}
      onChange={(e) => {
        const newValue = e.target.value;
        console.log("select Change!! : ", newValue);
        setter(newValue);
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