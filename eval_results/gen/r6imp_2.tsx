import React, { useState } from 'react';
import SearchIcon from './icons/SearchIcon';
import { debounce } from '../utils/debounce';

interface SearchBarProps {
  onSearch: (value: string) => void;
  placeholder: string;
}

function SearchBar({ onSearch, placeholder }: SearchBarProps) {
  const [value, setValue] = useState<string>('');
  const handleChange = debounce((v: string) => onSearch(v), 300);
  return (
    <div>
      <SearchIcon />
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          setValue(e.target.value);
          handleChange(e.target.value);
        }}
      />
    </div>
  );
}

export default SearchBar;