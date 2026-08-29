interface OptionItem {
  label: string;
  value: string;
}

interface EgovSelectProps {
  id: string;
  name: string;
  title: string;
  options: OptionItem[];
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
      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
        console.log("select Change!! : ", e.target.value);
        setter(e.target.value);
      }}
    >
      {options.map((option: OptionItem, i: number) => {
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