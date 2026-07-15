import React from 'react';

interface EgovSelectProps {
  id: string;
  name: string;
  title: string;
  options: { label: string; value: string }[];
  setValue: string;
  setter: (value: string) => void;
}

const EgovSelect: React.FC<EgovSelectProps> = ({ id, name, title, options, setValue, setter }) => {
  console.log("egovSelect", id, name, title, options, setValue, setter);

  const handleChange = () => {
    console.log("select Change!! : ", setValue);
    setter(setValue);
  };

  return (
    <select
      id={id}
      name={name}
      title={title}
      defaultValue={setValue}
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