import React from 'react';

interface Option {
  value: string;
  label: string;
}

interface Props {
  id: string;
  name: string;
  title: string;
  options: Option[];
  setValue: string;
  setter: (value: string) => void;
}

const EgovSelect: React.FC<Props> = ({ id, name, title, options, setValue, setter }) => {
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
      {options.map((option, i) => (
        <option key={i} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
};

export default EgovSelect;