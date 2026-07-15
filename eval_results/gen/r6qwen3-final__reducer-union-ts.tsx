import { Reducer } from 'react';

interface Todo {
  id: number;
  text: string;
  done: boolean;
}

type AddAction = { type: 'add'; payload: Omit<Todo, 'id'> };
type RemoveAction = { type: 'remove'; payload: number };
type ToggleAction = { type: 'toggle'; payload: number };

export type Action = AddAction | RemoveAction | ToggleAction;

function todosReducer(todos: Todo[], action: Action): Todo[] {
  const { type, payload } = action;
  switch (type) {
    case 'add': return [...todos, { ...payload, id: Date.now() }];
    case 'remove': return todos.filter((t) => t.id !== payload);
    case 'toggle': return todos.map((t) =>
      t.id === payload ? { ...t, done: !t.done } : t
    );
    default: throw new Error(`Unknown action: ${action.type}`);
  }
}

export interface TodosState { value: Todo[]; dispatch: React.Dispatch<Action>; }

const initialState: Todo[] = [];
function useTodos(): TodosState {
  const [value, dispatch] = React.useReducer<Reducer<Todo[], Action>>(todosReducer, initialState);
  return { value, dispatch };
}

export { Action };