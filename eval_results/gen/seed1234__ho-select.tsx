import React from 'react';

interface Option { value: string; label: string; }
interface Props { id: string; name: string; title: string; options: Option[]; setValue: string; setter: (v: string) => void; }

function EgovSelect({ id, name, title, options, setValue, setter }: Props): JSX.Element {
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
      {options.map((option, i) => (
        <option key={i} value={option.value}>{option.label}</option>
      ))}
    </select>
  );
}

export default EgovSelect;