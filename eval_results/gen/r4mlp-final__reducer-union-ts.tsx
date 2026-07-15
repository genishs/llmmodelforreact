import { Reducer, Dispatch } from 'react';

export type Todo = { id: number; text: string; done: boolean };
type Action = { type: 'ADD'; text: string }
  | { type: 'REMOVE'; id: number }
  | { type: 'TOGGLE'; id: number };

const reducer: Reducer<Todo[], Action> = (todos, action) => {
  switch (action.type) {
    case 'ADD': return [...todos, { id: Date.now(), text: action.text, done: false }];
    case 'REMOVE': return todos.filter((t) => t.id !== action.id);
    case 'TOGGLE': return todos.map((t) => (t.id === action.id ? { ...t, done: !t.done } : t));
    default: return todos;
  }
};

export function useTodos(): [Todo[], Dispatch<Action>] {
  const [state, dispatch] = React.useReducer(reducer, []);
  return [state, dispatch];
}