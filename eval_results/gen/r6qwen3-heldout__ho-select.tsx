import React from 'react';

interface OptionType { label: string; value: any; }
interface Props { id?: string; name?: string; title?: string; options: OptionType[]; setValue: any; setter: (v: any) => void; }

const EgovSelect = ({ id, name, title, options, setValue }: Props): JSX.Element => {
  const handleChange = () => {
    console.log('select Change!!', setValue);
    if (!setValue || typeof setValue === 'string') return;
    setValue();
  };
  return (
    <select id={id ?? ''} name={name ?? ''} title={title ?? ''}
      defaultValue={String(setValue)}
      onChange={handleChange}
    >
      {options.map((opt, idx) => (
        <option key={idx} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  );
};

export default EgovSelect;