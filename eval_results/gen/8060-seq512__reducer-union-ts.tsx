import { Reducer } from 'react';

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

export type TodoState = Todo[];

const initialState: TodoState = [];

const todoReducer: Reducer<TodoState, TodoAction> = (state = initialState, action) => {
  switch (action.type) {
    case 'ADD':
      return [...state, { id: Date.now(), text: action.payload.text, completed: false }];
    case 'REMOVE':
      return state.filter(todo => todo.id !== action.payload.id);
    case 'TOGGLE':
      return state.map(todo =>
        todo.id === action.payload.id ? { ...todo, completed: !todo.completed } : todo
      );
    default:
      return state;
  }
};