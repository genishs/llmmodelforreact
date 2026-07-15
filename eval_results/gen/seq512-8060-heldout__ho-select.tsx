import React, { useState } from 'react';

interface EgovSelectProps {
  id: string;
  name: string;
  title: string;
  options: { label: string; value: string }[];
  setValue: string;
  setter: (value: string) => void;
}

const EgovSelect: React.FC<EgovSelectProps> = ({ id, name, title, options, setValue, setter }) => {
  const [selectedValue, setSelectedValue] = useState<string>(setValue);

  console.log("egovSelect", id, name, title, options, setValue, setter);

  const handleChange = () => {
    console.log("select Change!! : ", selectedValue);
    setter(selectedValue);
  };

  return (
    <select
      id={id}
      name={name}
      title={title}
      defaultValue={selectedValue}
      onChange={handleChange}
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
};

export default EgovSelect;