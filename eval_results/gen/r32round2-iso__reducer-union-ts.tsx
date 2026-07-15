import { Reducer, Dispatch } from 'react';

export type Todo = { id: number; text: string; done: boolean };
type AddAction = { type: 'ADD'; text: string };
type RemoveAction = { type: 'REMOVE'; id: number };
type ToggleAction = { type: 'TOGGLE'; id: number };
export type TodoAction = AddAction | RemoveAction | ToggleAction;

function reducer(state: Todo[], action: TodoAction): Todo[] {
  switch (action.type) {
    case 'ADD':
      return [...state, { id: Date.now(), text: action.text, done: false }];
    case 'REMOVE':
      return state.filter((t) => t.id !== action.id);
    case 'TOGGLE':
      return state.map((t) =>
        t.id === action.id ? { ...t, done: !t.done } : t
      );
    default:
      throw new Error('Unhandled action');
  }
}

export function useTodos(): [Todo[], Dispatch<TodoAction>] {
  const [todos, dispatch] = React.useReducer<Reducer<Todo[], TodoAction>>(reducer, []);
  return [todos, dispatch];
}