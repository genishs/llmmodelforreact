import React from "react";

interface OptionType {
  label: string;
  value: string | number;
}

interface Props {
  id?: string;
  name?: string;
  title?: string;
  options: OptionType[];
  setValue: string | number;
  setter: (value: string | number) => void;
}

const EgovSelect = ({
  id,
  name,
  title,
  options,
  setValue,
  setter,
}: Props): JSX.Element => {
  console.log(
    "egovSelect",
    id,
    name,
    title,
    options,
    setValue,
    setter
  );

  const handleChange = (): void => {
    console.log("select Change!! :", setValue);
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