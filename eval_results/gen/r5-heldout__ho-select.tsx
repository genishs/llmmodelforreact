import React from "react";

interface Option {
  value: string;
  label: string;
}

interface EgovSelectProps {
  id: string;
  name: string;
  title: string;
  options: Option[];
  setValue: string;
  setter: (value: string) => void;
}

function EgovSelect({ id, name, title, options, setValue, setter }: EgovSelectProps): JSX.Element {
  console.log("egovSelect", id, name, title, options, setValue, setter);
  return (
    <select
      id={id}
      name={name}
      title={title}
      defaultValue={setValue}
      onChange={(e) => {
        const selectedValue = e.target.value;
        console.log("select Change!! : ", selectedValue);
        setter(selectedValue);
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