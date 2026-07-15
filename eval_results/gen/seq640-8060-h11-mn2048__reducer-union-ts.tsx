import { Dispatch } from 'react';

export type Todo = {
  id: number;
  text: string;
  completed: boolean;
};

type AddAction = {
  type: 'ADD';
  payload: { text: string };
};

type RemoveAction = {
  type: 'REMOVE';
  payload: { id: number };
};

type ToggleAction = {
  type: 'TOGGLE';
  payload: { id: number };
};

export type TodoAction = AddAction | RemoveAction | ToggleAction;

export type TodoState = {
  todos: Todo[];
};

const initialState: TodoState = {
  todos: [],
};

export const todoReducer = (state: TodoState, action: TodoAction): TodoState => {
  switch (action.type) {
    case 'ADD':
      return {
        ...state,
        todos: [
          ...state.todos,
          { id: Date.now(), text: action.payload.text, completed: false },
        ],
      };
    case 'REMOVE':
      return {
        ...state,
        todos: state.todos.filter(todo => todo.id !== action.payload.id),
      };
    case 'TOGGLE':
      return {
        ...state,
        todos: state.todos.map(todo =>
          todo.id === action.payload.id ? { ...todo, completed: !todo.completed } : todo
        ),
      };
    default:
      throw new Error();
  }
};