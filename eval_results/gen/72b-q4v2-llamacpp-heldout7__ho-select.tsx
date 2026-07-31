interface IEgovSelectProps {
  id: string;
  name: string;
  title?: string;
  options: Array<{ label: string; value: string }>;
  setValue: string;
  setter: (value: string) => void;
}

function EgovSelect({ id, name, title, options, setValue, setter }: IEgovSelectProps) {
  console.log("egovSelect", id, name, title, options, setValue, setter);
  return (
    <select
      id={id}
      name={name}
      title={title}
      defaultValue={setValue}
      onChange={() => {
        console.log("select Change!! : ", setValue);
        setter(setValue);
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