import React from 'react';
import Button from './Button';
import classNames from 'classnames';

interface ToolbarAction {
  id: number;
  label: string;
  onClick: () => void;
}

interface ToolbarProps {
  actions: ToolbarAction[];
  align: 'left' | 'right';
}

function Toolbar({ actions, align }: ToolbarProps) {
  return (
    <div className={classNames('toolbar', align)}>
      {actions.map((a) => (
        <Button key={a.id} onClick={a.onClick}>{a.label}</Button>
      ))}
    </div>
  );
}

export default Toolbar;