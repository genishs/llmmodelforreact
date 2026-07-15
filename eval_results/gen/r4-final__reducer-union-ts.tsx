import { Reducer } from 'react';

export type Todo = { id: number; text: string; done: boolean };
type AddAction = { type: 'ADD'; text: string };
type RemoveAction = { type: 'REMOVE'; id: number };
type ToggleAction = { type: 'TOGGLE'; id: number };
export type TodoAction = AddAction | RemoveAction | ToggleAction;

interface State {
  list: Todo[];
  nextId: number;
}

const initialState: State = { list: [], nextId: 0 };

function reducer(state: State, action: TodoAction): State {
  switch (action.type) {
    case 'ADD':
      return { ...state, list: [...state.list, { id: state.nextId++, text: action.text, done: false }] };
    case 'REMOVE': return { ...state, list: state.list.filter(t => t.id !== action.id) };
    case 'TOGGLE': return { ...state, list: state.list.map(t => t.id === action.id ? { ...t, done: !t.done } : t) };
    default: throw new Error('Unknown action');
  }
}