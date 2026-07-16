import { Reducer } from 'react';

// Define the Todo type
export interface Todo {
  id: number;
  text: string;
  completed: boolean;
}

// Define the action types and payloads using a discriminated union
type AddTodoAction = {
  type: 'ADD';
  payload: { text: string };
};

type RemoveTodoAction = {
  type: 'REMOVE';
  payload: { id: number };
};

type ToggleTodoAction = {
  type: 'TOGGLE';
  payload: { id: number };
};

// Union of all actions
export type TodoAction = AddTodoAction | RemoveTodoAction | ToggleTodoAction;

// Initial state for the todos list
const initialState: Todo[] = [];

// The reducer function to handle different actions
export const todoReducer: Reducer<Todo[], TodoAction> = (state = initialState, action) => {
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
      throw new Error(`Unhandled action type: ${action.type}`);
  }
};