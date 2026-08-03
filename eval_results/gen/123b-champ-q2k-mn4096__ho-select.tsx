import React from 'react';

interface OptionType {
  value: string;
  label: string;
}

interface EgovSelectProps {
  id: string;
  name: string;
  title: string;
  options: OptionType[];
  setValue: string;
  setter: (value: string) => void;
}

function EgovSelect({ id, name, title, options, setValue, setter }: EgovSelectProps) {
  console.log("egovSelect", id, name, title, options, setValue, setter);
  return (
    // ... rest of the code remains unchanged
    );
}

export default EgovSelect;